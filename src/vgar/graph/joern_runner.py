"""Run Joern's Python frontend in Docker and read back the facts of joern/export.sc (plan L3-1)."""
from __future__ import annotations

import importlib.util
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Literal

from vgar.graph.code_graph import JoernMethod, parse_export
from vgar.graph.docker_step import run_step

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "ghcr.io/joernio/joern@sha256:26571901cb0311b98013ad73c5078c979da690147ce2d3d9b41d707da556f122"
_SCRIPTS = Path(__file__).parent / "joern"
_END_OF_EXPORT = "\nEND\n"
# Runs as root in the container; a Linux host could not delete the output without the chmod.
_FINISH = "; code=$?; chmod -R a+rwX /out; exit $code"
_STEPS = (
    ("parse", "joern-parse /src --language PYTHONSRC -o /out/cpg.bin" + _FINISH),
    ("export", "joern --script /work/export.sc --param cpgFile=/out/cpg.bin --param outFile=/out/edges.tsv" + _FINISH),
)


@dataclass(frozen=True)
class JoernConfig:
    """Where and how long Joern may run."""

    image: str = DEFAULT_IMAGE
    docker: str = "docker"
    timeout_seconds: float = 900.0


@dataclass(frozen=True)
class JoernResult:
    """Outcome of one Joern run; anything but "ready" leaves the graph without G_code."""

    status: Literal["ready", "unavailable", "failed", "timeout"]
    reason: str | None = None
    methods: tuple[JoernMethod, ...] = ()


def docker_command(config: JoernConfig, name: str, staging: PurePath, out: PurePath, scripts: PurePath, shell_script: str) -> list[str]:
    """Build the command of one container; each mount stays a single argument whatever the path holds."""
    return [config.docker, "run", "--rm", "--name", name, "--network", "none",
            "-v", f"{staging.as_posix()}:/src:ro", "-v", f"{out.as_posix()}:/out", "-v", f"{scripts.as_posix()}:/work:ro",
            config.image, "sh", "-c", shell_script]


def _run_container(config: JoernConfig, name: str, staging: Path, out: Path, script: str, deadline: float) -> JoernResult | None:
    """Run one step; return the failure, or None when it succeeded."""
    failure = run_step(config.docker, name, docker_command(config, name, staging, out, _SCRIPTS, script), deadline,
                       f"Joern exceeded {config.timeout_seconds} s")
    if failure is None:
        return None
    logger.warning("Joern step %s: %s", failure.status, failure.reason)
    return JoernResult(failure.status, failure.reason)


def run_joern(root: Path, python_files: list[Path], config: JoernConfig) -> JoernResult:
    """Analyse the given files of a repository with Joern.

    Args:
        root: Repository root; paths in the result are relative to it.
        python_files: Absolute paths of the files to analyse; Joern sees no others.
        config: Image, Docker executable and the time limit for all steps together.

    Returns:
        The parsed methods when status is "ready"; otherwise the status and a reason. Never raises for a Docker problem.
    """
    if importlib.util.find_spec("networkx") is None:
        return JoernResult("unavailable", "networkx is not installed; install the code-graph extra")
    if not python_files:
        return JoernResult("ready")
    deadline = time.monotonic() + config.timeout_seconds
    try:
        with tempfile.TemporaryDirectory(prefix="vgar-joern-", ignore_cleanup_errors=True) as temporary:
            return _analyse(Path(temporary), root, python_files, config, deadline)
    except OSError as error:
        return JoernResult("failed", f"cannot prepare the files for Joern: {error}")


def _read_export(path: Path) -> list[JoernMethod]:
    """Read the export; every Python file gives at least a <module> method, so none at all means it is broken."""
    text = path.read_bytes().decode("utf-8", "replace")
    if not text.endswith(_END_OF_EXPORT):
        raise ValueError("the export is empty or incomplete")
    methods = parse_export(text)
    if not methods:
        raise ValueError("the export has no methods")
    return methods


def _analyse(temporary: Path, root: Path, python_files: list[Path], config: JoernConfig, deadline: float) -> JoernResult:
    staging, out = temporary / "src", temporary / "out"
    out.mkdir()
    for path in python_files:
        target = staging / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    stem = f"vgar-joern-{uuid.uuid4().hex}"
    for step, script in _STEPS:
        failure = _run_container(config, f"{stem}-{step}", staging, out, script, deadline)
        if failure is not None:
            return failure
    try:
        return JoernResult("ready", methods=tuple(_read_export(out / "edges.tsv")))
    except (OSError, ValueError) as error:
        return JoernResult("failed", f"unreadable Joern export: {error}")
