"""Run JARVIS in its own Docker image and read back the call graph (plan L2-1)."""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePath, PurePosixPath
from typing import Literal

from vgar.graph.docker_step import run_step

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "vgar/jarvis-analyzer:v1.0"
JARVIS_COMMIT = "8871b86494a1aec0095686ffa543994a7361af88"
BUILD_COMMAND = "docker build -t vgar/jarvis-analyzer:v1.0 src/vgar/graph/jarvis"
_INSPECT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class JarvisConfig:
    """Where and how long JARVIS may run."""

    image: str = DEFAULT_IMAGE
    docker: str = "docker"
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class JarvisResult:
    """Outcome of one JARVIS run; anything but "ready" leaves the graph to SCIP or the static resolver."""

    status: Literal["ready", "unavailable", "failed", "timeout"]
    reason: str | None = None
    graph: dict[str, list[str]] = field(default_factory=dict)
    skipped_files: tuple[str, ...] = ()


def staged_path(relative_path: str, root: Path, source_roots: tuple[str, ...]) -> str:
    """Return where a repository file goes for JARVIS, so that imports inside a source root resolve.

    A source root that is itself a package, like xarray/, keeps its name: absolute imports use it.
    """
    first, _, rest = relative_path.partition("/")
    if rest and first in source_roots and not (root / first / "__init__.py").is_file():
        return rest
    return relative_path


def module_name_of(staged: str) -> str:
    """Return the module name JARVIS gives a staged file."""
    parts = list(PurePosixPath(staged).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def jarvis_command(config: JarvisConfig, name: str, staging: PurePath, out: PurePath) -> list[str]:
    """Build the docker command; each mount stays a single argument whatever the path holds."""
    return [config.docker, "run", "--rm", "--name", name, "--network", "none", "-e", "PYTHONHASHSEED=0",
            "-v", f"{staging.as_posix()}:/src:ro", "-v", f"{out.as_posix()}:/out", config.image]


def _read_output(out: Path) -> tuple[dict[str, list[str]], list[str]]:
    graph = json.loads((out / "graph.json").read_bytes().decode("utf-8", "replace"))
    skipped = json.loads((out / "skipped.json").read_bytes().decode("utf-8", "replace"))
    lists = [skipped, *graph.values()] if isinstance(graph, dict) else [None]
    if not all(isinstance(names, list) and all(isinstance(name, str) for name in names) for names in lists):
        raise ValueError("graph.json must map names to lists of names and skipped.json must list names")
    return graph, skipped


def run_jarvis(root: Path, python_files: list[Path], source_roots: tuple[str, ...], config: JarvisConfig) -> JarvisResult:
    """Analyse the given files of a repository with JARVIS.

    Args:
        root: Repository root.
        python_files: Absolute paths of the files to analyse; JARVIS sees no others.
        source_roots: The builder's source roots, which decide where each file is staged.
        config: Image, Docker executable and time limit.

    Returns:
        The call graph when status is "ready"; otherwise the status and a reason. Never raises for a Docker problem.
    """
    if not python_files:
        return JarvisResult("ready")
    inspect = run_step(config.docker, None, [config.docker, "image", "inspect", config.image],
                       time.monotonic() + _INSPECT_TIMEOUT_SECONDS, "docker image inspect timed out")
    if inspect is not None:
        return JarvisResult("unavailable", f"{inspect.reason}; build the image with: {BUILD_COMMAND}")
    deadline = time.monotonic() + config.timeout_seconds
    try:
        with tempfile.TemporaryDirectory(prefix="vgar-jarvis-", ignore_cleanup_errors=True) as temporary:
            return _analyse(Path(temporary), root, python_files, source_roots, config, deadline)
    except OSError as error:
        return JarvisResult("failed", f"cannot prepare the files for JARVIS: {error}")


def _analyse(temporary: Path, root: Path, python_files: list[Path], source_roots: tuple[str, ...], config: JarvisConfig, deadline: float) -> JarvisResult:
    staging, out = temporary / "src", temporary / "out"
    staging.mkdir()
    out.mkdir()
    origin: dict[str, str] = {}
    skipped: set[str] = set()
    for path in python_files:
        relative = path.relative_to(root).as_posix()
        target = staged_path(relative, root, source_roots)
        if target in origin:
            skipped.add(relative)
            continue
        origin[target] = relative
        (staging / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, staging / target)
    name = f"vgar-jarvis-{uuid.uuid4().hex}"
    failure = run_step(config.docker, name, jarvis_command(config, name, staging, out), deadline,
                       f"JARVIS_TIMEOUT: exceeded {config.timeout_seconds} s")
    if failure is not None:
        logger.warning("JARVIS step %s: %s", failure.status, failure.reason)
        return JarvisResult(failure.status, failure.reason)
    try:
        graph, tool_skipped = _read_output(out)
    except (OSError, ValueError) as error:
        return JarvisResult("failed", f"unreadable JARVIS output: {error}")
    skipped.update(origin[path] for path in tool_skipped if path in origin)
    return JarvisResult("ready", graph=graph, skipped_files=tuple(sorted(skipped)))
