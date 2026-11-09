from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vgar.mcp.proposal.context import current_context
from vgar.mcp.proposal.locking import locked, no_links
from vgar.mcp.proposal.security import sanitize


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    event_type: str
    payload: dict[str, Any]


class AuditLogger:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self._path = no_links(path)
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def write(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        context = current_context()
        correlation = ({"request_id":context.request_id,"run_id":context.run_id,"task_id":context.task_id,"snapshot_hash":context.snapshot_hash} if context else {})
        event = AuditEvent(
            timestamp=datetime.now(
                UTC
            ).isoformat(),
            event_type=event_type,
            payload=sanitize({**payload,**correlation}),
        )

        raw=(json.dumps(asdict(event),ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8")
        if len(raw)>65536:
            raise ValueError("Audit record exceeds 65536 bytes")
        with locked(self._path.with_name(self._path.name+".lock")):
            no_links(self._path)
            with self._path.open("a+b") as file:
                size=file.seek(0,2)
                if size:
                    file.seek(-1,2)
                    if file.read(1)!=b"\n":
                        raise ValueError("Audit integrity: incomplete tail")
                file.seek(0,2); file.write(raw); file.flush(); os.fsync(file.fileno())
