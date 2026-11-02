"""Internal checker output; public evidence DTOs and artifact publication live elsewhere."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class CheckAnalysis:
    """Detached, JSON-ready analysis before a pipeline assigns ``details_ref``.

    ``details`` carries coverage and diagnostic evidence. It must not be used to
    infer PASS from a NOT_RUN/ERROR status. No source or artifact is written here.
    """

    status: Literal['PASS', 'FAIL', 'NOT_RUN', 'ERROR']
    reasons: tuple[str, ...]
    details: dict[str, Any]
