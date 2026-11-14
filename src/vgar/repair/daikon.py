"""L5-2 Daikon core: write Daikon's trace format from the L5-1 trace, run Daikon, read its output.

Daikon has no Python front end, so this module is one, limited to the values the trace plugin keeps.
Encoding rules found in the 14/11 spike:
* every trace that is checked uses the baseline's declarations (a value of another type becomes
  ``nonsensical``; an ``int`` is accepted where the baseline declared ``double``);
* a variable that is ``None`` at least once on the baseline also gets ``<name>_is_none`` (Daikon ignores
  ``null`` strings);
* object hashcodes are the plugin's stable ids (equal across runs).
Daikon runs only when ``VGAR_DAIKON_JAR`` and ``VGAR_JAVA_HOME`` are set; any failure raises
``DaikonUnavailable`` so the caller can use the Python fallback.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

FLAG = "_is_none"


class DaikonUnavailable(RuntimeError):
    """Daikon is not configured, missing, too slow for the deadline, or failed."""


@dataclass(frozen=True)
class DaikonConfig:
    jar: Path | None = None
    java_home: Path | None = None

    @classmethod
    def from_env(cls) -> DaikonConfig:
        """Read ``VGAR_DAIKON_JAR`` and ``VGAR_JAVA_HOME``.

        Raises:
            ValueError: A variable is set to a relative path.
        """
        values = {}
        for key, name in (("jar", "VGAR_DAIKON_JAR"), ("java_home", "VGAR_JAVA_HOME")):
            raw = os.environ.get(name, "").strip()
            if raw and not Path(raw).is_absolute():
                raise ValueError(f"{name} must be an absolute path")
            values[key] = Path(raw) if raw else None
        return cls(**values)

    @property
    def configured(self) -> bool:
        return self.jar is not None and self.java_home is not None


def _kind(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "java.lang.String"
    return "hashcode" if isinstance(value, dict) else None


def declarations(records: list[dict]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Per program point, one Daikon type per variable, for entry and exit (from the baseline records).

    Args:
        records: Baseline trace records (``raise`` records are ignored).
    """
    seen: dict[str, dict[str, dict[str, set]]] = {"enter": {}, "exit": {}}
    nones: dict[str, set[str]] = {}
    for record in records:
        if record["kind"] == "raise":
            continue
        point = seen[record["kind"]].setdefault(record["ppt"], {})
        for name, value in record["vars"].items():
            point.setdefault(name, set())
            if _kind(value):
                point[name].add(_kind(value))
            elif value is None and name != "return" and not name.startswith("return."):
                nones.setdefault(record["ppt"], set()).add(name)

    def single(points: dict[str, dict[str, set]]) -> dict[str, dict[str, str]]:
        out = {}
        for ppt, variables in points.items():
            kept = {}
            for name, kinds in sorted(variables.items()):
                if kinds == {"int", "double"}:
                    kinds = {"double"}
                if len(kinds) == 1:
                    kept[name] = next(iter(kinds))
            for name in sorted(nones.get(ppt, ())):
                if name in variables:
                    kept[name + FLAG] = "boolean"
            out[ppt] = kept
        return out

    enter, exit_ = single(seen["enter"]), single(seen["exit"])
    for ppt in exit_:
        exit_[ppt] = {k: v for k, v in exit_[ppt].items()
                      if k == "return" or k.startswith("return.") or enter.get(ppt, {}).get(k) == v}
    return enter, exit_


def _daikon_name(name: str, names: set[str]) -> str:
    if "." in name and name.rsplit(".", 1)[0] in names and not name.endswith(".__len__"):
        return name
    return name.replace(".__len__", "_size").replace(".", "_")


def _value(kind: str, value) -> tuple[str, int]:
    if value is None:
        return ("null", 1) if kind in ("java.lang.String", "hashcode") else ("nonsensical", 2)
    actual = _kind(value)
    if actual != kind and not (kind == "double" and actual == "int"):
        return "nonsensical", 2
    if kind == "boolean":
        return ("1" if value else "0"), 1
    if kind == "java.lang.String":
        return json.dumps(value), 1
    if kind == "hashcode":
        return str(value.get("__id__", 1)), 1
    return repr(value), 1


def _escape(ppt: str) -> str:
    return ppt.replace(" ", "\\_")


def _declare(lines: list[str], name: str, kind: str, names: set[str]) -> None:
    shown = _daikon_name(name, names)
    parent = name.rsplit(".", 1)[0] if shown == name and "." in name else None
    lines.append(f"variable {shown}")
    if parent:
        lines += [f"  var-kind field {name.rsplit('.', 1)[1]}", f"  enclosing-var {parent}"]
    else:
        lines.append("  var-kind return" if name == "return" else "  var-kind variable")
    lines.append(f"  dec-type {'java.lang.Object' if kind == 'hashcode' else kind}")
    lines.append(f"  rep-type {'int' if kind == 'boolean' else kind}")
    if "." not in name and name != "return" and not name.endswith(FLAG):
        lines.append("  flags is_param")


def write_dtrace(records: list[dict], path: Path, decls: tuple[dict, dict]) -> None:
    """Write declarations and samples in Daikon's format (one file).

    Args:
        records: Trace records to write (already limited to the selected tests).
        path: Output ``.dtrace`` file.
        decls: ``declarations`` of the baseline.
    """
    enter, exit_ = decls
    lines = ["decl-version 2.0", "var-comparability none", ""]
    for ppt in sorted(enter):
        for suffix, types, ppt_type in ((":::ENTER", enter[ppt], "enter"), (":::EXIT1", exit_.get(ppt, {}), "subexit")):
            lines += [f"ppt {_escape(ppt)}{suffix}", f"ppt-type {ppt_type}"]
            for name, kind in types.items():
                _declare(lines, name, kind, set(types))
            lines.append("")
    for record in records:
        if record["kind"] == "raise" or record["ppt"] not in enter:
            continue
        is_enter = record["kind"] == "enter"
        types = enter[record["ppt"]] if is_enter else exit_.get(record["ppt"], {})
        lines += [f"{_escape(record['ppt'])}{':::ENTER' if is_enter else ':::EXIT1'}", "this_invocation_nonce",
                  str(record["nonce"])]
        for name, kind in types.items():
            if name.endswith(FLAG) and name not in record["vars"]:
                base = name[:-len(FLAG)]
                text, modified = (("1" if record["vars"][base] is None else "0"), 1) if base in record["vars"] \
                    else ("nonsensical", 2)
            else:
                text, modified = _value(kind, record["vars"].get(name))
            lines += [_daikon_name(name, set(types)), text, str(modified)]
        lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_invariants(text: str) -> list[str]:
    """``PrintInvariants`` output → ``"<ppt>:::ENTER|EXIT[;condition]  <invariant>"`` lines."""
    out, ppt, header_next = [], None, False
    for line in text.splitlines():
        if line.startswith("====="):
            header_next = True
            continue
        if header_next:
            ppt, header_next = line.strip(), False
            continue
        if ppt and line.strip() and not line.startswith(("Exiting Daikon", "Daikon version")):
            out.append(f"{ppt}  {line.strip()}")
    return out


_VIOLATION = re.compile(r"At ppt (.+?):::(ENTER|EXIT)\d*(;condition=\"[^\"]*\")?, Invariant '(.*)' invalidated by sample")


def parse_violations(text: str) -> list[str]:
    """``InvariantChecker --verbose`` output → unique ``"<ppt>:::ENTER|EXIT  <invariant>"`` (EXITn merged)."""
    found = set()
    for line in text.splitlines():
        match = _VIOLATION.search(line)
        if match:
            found.add(f"{match.group(1)}:::{match.group(2)}{match.group(3) or ''}  {match.group(4)}")
    return sorted(found)


def parse_version(text: str) -> str | None:
    """Version from Daikon's banner line ``Daikon version X, released ...``."""
    match = re.search(r"Daikon version ([^,\s]+)", text)
    return match.group(1) if match else None


def run_daikon(config: DaikonConfig, base: Path, cand: Path, work: Path, deadline: float
               ) -> tuple[list[str], list[str], str | None]:
    """Infer on the baseline trace, check the candidate trace.

    Args:
        config: Daikon jar and Java home.
        base: Baseline ``.dtrace``.
        cand: Candidate ``.dtrace`` (written with the baseline's declarations).
        work: Folder for ``base.inv.gz``.
        deadline: ``time.monotonic()`` value by which all Daikon commands must finish.

    Returns:
        Learned invariants, violated invariants and the Daikon version.

    Raises:
        DaikonUnavailable: Not configured, jar missing, deadline reached or a command failed.
    """
    if not config.configured:
        raise DaikonUnavailable("not configured")
    assert config.jar is not None and config.java_home is not None
    if not config.jar.is_file():
        raise DaikonUnavailable(f"jar missing: {config.jar}")
    java = str(config.java_home / "bin" / ("java.exe" if os.name == "nt" else "java"))
    inv = Path(work) / "base.inv.gz"

    def call(tool: str, *args: str) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DaikonUnavailable("deadline reached")
        try:
            process = subprocess.run([java, "-cp", str(config.jar), tool, *args], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=remaining, check=False)
        except subprocess.TimeoutExpired as error:
            raise DaikonUnavailable("deadline reached") from error
        except OSError as error:
            raise DaikonUnavailable(f"{tool}: {type(error).__name__}") from error
        if process.returncode != 0:
            raise DaikonUnavailable(f"{tool} exit {process.returncode}: {(process.stderr or '')[-200:].strip()}")
        return process.stdout or ""

    banner = call("daikon.Daikon", "--no_text_output", "-o", str(inv), str(base))
    learned = parse_invariants(call("daikon.PrintInvariants", str(inv)))
    violated = parse_violations(call("daikon.tools.InvariantChecker", "--verbose", str(inv), str(cand)))
    return learned, violated, parse_version(banner)
