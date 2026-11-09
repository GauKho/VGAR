"""Run one Docker command under a deadline and report problems as values, never as exceptions (shared by the analyzers)."""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

_REMOVE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class StepFailure:
    """Why a Docker step did not succeed."""

    status: Literal["unavailable", "failed", "timeout"]
    reason: str


def _remove_container(docker: str, name: str) -> None:
    try:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=_REMOVE_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("could not remove container %s: %s", name, error)


def run_step(docker: str, name: str | None, command: list[str], deadline: float, timeout_reason: str) -> StepFailure | None:
    """Run the command; return the failure, or None when it succeeded.

    Args:
        docker: The Docker executable, used to remove the container after a timeout.
        name: The container to remove after a timeout; None when the command starts no container.
        command: The full command, run without a shell. Its output is captured, never printed.
        deadline: The time.monotonic() value to stop at.
        timeout_reason: The reason to report when the deadline passes.

    Returns:
        None on success; otherwise the status and reason.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return StepFailure("timeout", timeout_reason)
    try:
        done = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=remaining, check=False)
    except subprocess.TimeoutExpired:
        if name is not None:
            _remove_container(docker, name)  # killing the docker client leaves the container running
        return StepFailure("timeout", timeout_reason)
    except OSError as error:
        return StepFailure("unavailable", f"cannot run {docker}: {error}")
    if done.returncode != 0:
        output = (done.stderr or done.stdout or "").strip().splitlines()
        return StepFailure("failed", f"exit code {done.returncode}: {output[-1][:300] if output else 'no output'}")
    return None
