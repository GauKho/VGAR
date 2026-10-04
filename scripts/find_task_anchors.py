from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.graph.grounding import TaskAnchorFinder


def main() -> None:
    parser = argparse.ArgumentParser(description="Find M1 task anchors in a graph snapshot.")
    parser.add_argument("graph", type=Path)
    issue = parser.add_mutually_exclusive_group(required=True)
    issue.add_argument("--issue-text")
    issue.add_argument("--issue-file", type=Path)
    parser.add_argument("--failing-test", action="append", default=[])
    args = parser.parse_args()
    text = args.issue_file.read_text(encoding="utf-8") if args.issue_file else args.issue_text
    document = json.loads(args.graph.read_text(encoding="utf-8"))
    result = TaskAnchorFinder(document).find_task_anchors(text, args.failing_test)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()