"""Optional tree-sitter-graph fact source (plan task L1-1; proposal §5.2 Layer 1).

Runs the tree-sitter-graph CLI with the rules in ``tsg/python.tsg`` on one file and returns its graph
as plain facts; ``PythonGraphBuilder`` merges them into its document. When the CLI cannot run, the
build keeps the plain graph (proposal line 1476: "lightweight core + optional precision backends").

The CLI (tree-sitter-graph 0.12) links tree-sitter 0.24, so the grammar it loads must be
tree-sitter-python v0.23.6 (ABI 14), listed under "parser-directories" in
``<tree_sitter_dir>/config.json``. Compiling that grammar on first use needs a C compiler on PATH.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_RULES = Path(__file__).with_name("tsg") / "python.tsg"


@dataclass(frozen=True)
class TsgConfig:
    executable: Path
    tree_sitter_dir: Path
    rules: Path = DEFAULT_RULES
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> TsgConfig | None:
        """VGAR_TSG_EXECUTABLE + VGAR_TSG_TREE_SITTER_DIR, or None when either is unset."""
        executable = os.getenv("VGAR_TSG_EXECUTABLE", "").strip()
        tree_sitter_dir = os.getenv("VGAR_TSG_TREE_SITTER_DIR", "").strip()
        if not executable or not tree_sitter_dir:
            return None
        return cls(executable=Path(executable), tree_sitter_dir=Path(tree_sitter_dir))


@dataclass
class TsgFileFacts:
    """One file's graph: CLI node id -> attributes, and (source id, sink id, edge type) triples."""

    nodes: dict[int, dict[str, Any]] = field(default_factory=dict)
    edges: list[tuple[int, int, str]] = field(default_factory=list)


class TsgError(RuntimeError):
    """The CLI could not produce a graph for one file."""


def check_available(config: TsgConfig) -> tuple[str | None, str | None]:
    """Return (reason the CLI cannot be used, CLI version string)."""
    for label, path in (("executable", config.executable), ("rules", config.rules),
                        ("tree_sitter_dir", config.tree_sitter_dir)):
        if not path.exists():
            return f"tree-sitter-graph {label} not found: {path}", None
    try:
        done = subprocess.run([str(config.executable), "--version"], capture_output=True, text=True,
                              timeout=config.timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"cannot run tree-sitter-graph: {error}", None
    if done.returncode != 0:
        return f"tree-sitter-graph --version failed: {done.stderr.strip()}", None
    return None, done.stdout.strip()


def run_file(config: TsgConfig, root: Path, relative_path: str) -> TsgFileFacts:
    """Run the rules on ``root / relative_path``; raise TsgError when the CLI fails."""
    command = [str(config.executable), str(config.rules), str(root / relative_path),
               "--scope", "source.python", "--json", "--allow-parse-errors"]
    env = {**os.environ, "TREE_SITTER_DIR": str(config.tree_sitter_dir),
           "TREE_SITTER_LIBDIR": str(config.tree_sitter_dir / "lib")}
    try:
        done = subprocess.run(command, env=env, capture_output=True, timeout=config.timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TsgError(f"{relative_path}: {error}") from error
    if done.returncode != 0:
        raise TsgError(f"{relative_path}: {done.stderr.decode('utf-8', 'replace').strip()}")
    try:
        return parse_graph(json.loads(done.stdout.decode("utf-8")))
    except (ValueError, KeyError, TypeError) as error:
        raise TsgError(f"{relative_path}: unreadable tree-sitter-graph JSON: {error}") from error


def _value(raw: Any) -> Any:
    """Unwrap a typed JSON value such as {"type": "string", "string": "x"}."""
    if isinstance(raw, dict) and "type" in raw and len(raw) == 2:
        return next(value for key, value in raw.items() if key != "type")
    return raw


def parse_graph(raw: list[dict[str, Any]]) -> TsgFileFacts:
    """Turn the CLI's ``--json`` output (a list of nodes with nested edges) into facts."""
    facts = TsgFileFacts()
    for item in raw:
        facts.nodes[item["id"]] = {key: _value(value) for key, value in item.get("attrs", {}).items()}
        for edge in item.get("edges", []):
            facts.edges.append((item["id"], edge["sink"], _value(edge.get("attrs", {}).get("type"))))
    return facts
