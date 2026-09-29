from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


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
        self._path = path
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def write(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        event = AuditEvent(
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            event_type=event_type,
            payload=payload,
        )

        with self._path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    asdict(event),
                    ensure_ascii=False,
                )
            )
            file.write("\n")