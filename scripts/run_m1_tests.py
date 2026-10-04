"""Run only M1 tests, using this checkout as the package source."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    "test_graph_schema.py",
    "test_graph_builder.py",
    "test_context_contract.py",
    "test_sqlite_graph_service.py",
    "test_end_to_end_graph_pipeline.py",
    "test_task_anchors.py",
    "test_task_overlay.py",
    "test_graph_retrieval.py",
    "test_token_counter.py",
)


def main() -> int:
    source = str(ROOT / "src")
    sys.path.insert(0, source)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        filter(None, (source, os.environ.get("PYTHONPATH", "")))
    )
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for pattern in PATTERNS:
        suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
