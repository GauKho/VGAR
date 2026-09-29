from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)

AUDIT_FILE = (
    PROJECT_ROOT
    / "logs"
    / "mcp_audit.jsonl"
)


def write_audit(
    *,
    tool: str,
    arguments: dict[str, Any],
    status: str,
) -> None:
    AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "tool": tool,
        "arguments": arguments,
        "status": status,
    }

    with AUDIT_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )