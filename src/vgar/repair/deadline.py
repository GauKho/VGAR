"""Trusted-fixture guard and deadline-bounded native executor shared by the MCP test providers.

Moved unchanged from the removed M2 generation pipeline (spec 2026-11-12 §4.1b).
"""
import json
import time

from vgar.repair.config import CONFIG_DIR
from vgar.repair.executor import GLOBAL_DEADLINE, NativeExecutor
from vgar.repair.workspace import inventory


class StopRun(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def require_trusted_fixture(task):
    registry = json.loads((CONFIG_DIR / 'trusted_fixtures.json').read_text(encoding='utf-8'))
    approved = registry.get(task.task_id)
    if (not task.trusted_fixture or not approved or sorted(task.allowed_source_paths) != sorted(approved['allowed'])
            or inventory(task.source_repo) != {p: 'sha256:' + h for p, h in approved['files'].items()}):
        raise ValueError('Native execution only allowed on byte-verified approved fixtures')


class DeadlineExecutor(NativeExecutor):
    def __init__(self, lease, deadline, output_cap, *, cancel_event=None):
        super().__init__(lease, output_cap, cancel_event=cancel_event)
        self.deadline = deadline

    def run(self, argv, cwd, timeout_seconds):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(GLOBAL_DEADLINE)
        return super().run(argv, cwd, min(timeout_seconds, remaining))
