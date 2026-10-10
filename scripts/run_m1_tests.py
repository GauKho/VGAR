"""Run only M1 tests, using this checkout as the package source."""
from __future__ import annotations

import os
import sys
import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    "test_graph_schema.py",
    "test_graph_builder.py",
    "test_graph_builder_robustness.py",
    "test_context_contract.py",
    "test_sqlite_graph_service.py",
    "test_end_to_end_graph_pipeline.py",
    "test_task_anchors.py",
    "test_task_overlay.py",
    "test_graph_retrieval.py",
    "test_token_counter.py",
    "test_w5_w6_mcp.py",
)


def main() -> int:
    source = str(ROOT / "src")
    sys.path.insert(0, source)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        filter(None, (source, os.environ.get("PYTHONPATH", "")))
    )
    return pytest.main(["-q", *(str(ROOT / "tests" / name) for name in PATTERNS), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
