"""Opt-in JSONL diagnostics. Never write to the MCP stdio protocol stream."""
from __future__ import annotations

import json
import os
import time
import uuid
import logging
from pathlib import Path
from typing import Any


class GraphTrace:
    def __init__(self, path: str | Path | None = None, *, run_id: str | None = None) -> None:
        value = path or os.getenv("VGAR_GRAPH_DEBUG_LOG")
        self.path = Path(value) if value else None
        self.run_id = run_id or os.getenv("VGAR_GRAPH_DEBUG_RUN_ID") or os.getenv("VGAR_TRACE_RUN_ID") or uuid.uuid4().hex

    def emit(self, event: str, **fields: Any) -> None:
        if self.path is None:
            return
        row = {"time_unix": time.time(), "run_id": self.run_id, "event": event, **fields}
        # Code/snippets are deliberately not included by callers.
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except OSError as error:
            logging.getLogger(__name__).warning("Graph debug log disabled: %s", error)
            self.path = None
