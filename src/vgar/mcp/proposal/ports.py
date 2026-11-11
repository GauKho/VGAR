"""Trusted immutable provider registration. No dynamic imports or model-selected plugins."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Protocol

from vgar.repair.workspace import safe_relative_path

from . import contracts as c
from .context import BoundContext

METHODS = {"build": "build_or_update", "path": "explain_path", "traversal": "traverse",
           "verification": "verify_graph", "ranking": "rank_candidates", "tests": "run_diff_tests",
           **{"resource_" + name: "snapshot_resource" for name in ("schema", "component", "task", "baseline")}}


class GraphProvider(Protocol):
    async def build_or_update(self, request: c.BuildRequest, context: BoundContext) -> c.BuildResult: ...
    def explain_path(self, request: c.PathRequest, context: BoundContext) -> c.PathResult: ...
    def traverse(self, request: c.TraversalRequest, context: BoundContext) -> c.TraversalResult: ...
    def snapshot_resource(self, request: c.ResourceRequest, context: BoundContext) -> c.ResourceResult: ...


class VerificationProvider(Protocol):
    def verify_graph(self, request: c.DiffRequest, context: BoundContext) -> c.CheckEvidence: ...
    def rank_candidates(self, request: c.RankRequest, context: BoundContext) -> c.RankResult: ...


class TestProvider(Protocol):
    async def run_diff_tests(self, request: c.DiffRequest, context: BoundContext) -> c.TestEvidence: ...


@dataclass(frozen=True)
class ProviderBinding:
    provider: Any
    binding: c.SnapshotBinding
    capabilities: frozenset[str]
    synthetic: bool = False
    lifecycle: str | None = None
    candidate_workspace: str | None = None

    def __post_init__(self):
        if type(self.capabilities) is not frozenset or not self.capabilities or self.capabilities - METHODS.keys():
            raise ValueError("Invalid provider capabilities")
        if type(self.binding) is not c.SnapshotBinding or type(self.synthetic) is not bool:
            raise ValueError("Invalid provider binding")


@dataclass(frozen=True)
class ProviderRegistry:
    bindings: tuple[ProviderBinding, ...] = ()
    test_only: bool = False
    required_checks: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.bindings) is not tuple or type(self.required_checks) is not tuple or type(self.test_only) is not bool:
            raise ValueError("Immutable host configuration required")
        seen = set()
        if len(set(self.required_checks)) != len(self.required_checks) or any(not isinstance(x, str) or not x for x in self.required_checks):
            raise ValueError("Invalid required checks")
        for record in self.bindings:
            if type(record) is not ProviderBinding:
                raise ValueError("Host provider binding required")
            if record.synthetic and not self.test_only:
                raise ValueError("synthetic provider forbidden in production")
            if seen & record.capabilities:
                raise ValueError("Duplicate provider capability")
            seen.update(record.capabilities)
            for cap in record.capabilities:
                method = getattr(record.provider, METHODS[cap], None)
                if not callable(method):
                    raise TypeError("Provider method missing: " + METHODS[cap])
                if cap in {"build", "tests"} and (record.lifecycle != "guarded-v1" or not inspect.iscoroutinefunction(method)):
                    raise ValueError("Async guarded-v1 lifecycle required for writes/jobs")
                if cap == "tests":
                    if not isinstance(record.candidate_workspace, str):
                        raise ValueError("Host-bound candidate workspace required")
                    safe_relative_path(record.candidate_workspace)

    def get(self, capability):
        return next((record for record in self.bindings if capability in record.capabilities), None)
