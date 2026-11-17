"""Count held-out tasks by number of changed source files, for decision D3-1 (plan 2026-11-17 Task 7).

Checks every row with ``validate_task``, as ``prepare_dataset`` does (so it reads ``base_commit`` and
``problem_statement`` without printing them), then counts by the file paths of ``patch`` (``changed_source_files``);
prints counts, never task text. Each run, with the parquet's SHA-256, is appended to ``results/heldout_access.log``.

    python scripts/count_heldout_eligible.py <SWE-bench Verified parquet>
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.heldout_gate import ACCESS_LOG
from vgar.evaluation.retrieval.dataset import (
    changed_source_files,
    split_of,
    validate_task,
)
from vgar.evaluation.retrieval.evidence import sha256

COLUMNS = ["instance_id", "repo", "base_commit", "problem_statement", "patch"]


def count_eligible(rows: list[dict]) -> dict:
    """Held-out task count, and how many change at least 1 and at least 2 source files, overall and per repo.

    Raises ``ValueError`` on a row ``validate_task`` rejects, as ``prepare_dataset`` would.
    """
    for row in rows:
        validate_task(row)
    counts = {"heldout": 0, "at_least_1": 0, "at_least_2": 0}
    by_repo: dict[str, dict[str, int]] = defaultdict(lambda: {"at_least_1": 0, "at_least_2": 0})
    for row in rows:
        if split_of(row["instance_id"]) != "heldout":
            continue
        counts["heldout"] += 1
        try:
            files = len(changed_source_files(row["patch"]))
        except ValueError:
            continue
        for key, minimum in (("at_least_1", 1), ("at_least_2", 2)):
            if files >= minimum:
                counts[key] += 1
                by_repo[row["repo"]][key] += 1
    return {**counts, "by_repo": {repo: dict(values) for repo, values in sorted(by_repo.items())}}


def main(argv: list[str] | None = None) -> int:
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parquet", type=Path)
    args = parser.parse_args(argv)
    parquet_hash = sha256(args.parquet.read_bytes())
    counts = {"parquet_sha256": parquet_hash, **count_eligible(pq.read_table(args.parquet, columns=COLUMNS).to_pylist())}
    log = ROOT / ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": datetime.now(UTC).isoformat(), "user": getpass.getuser(),
                                 "command": "count_heldout_eligible", "parquet": str(args.parquet),
                                 "parquet_sha256": parquet_hash,
                                 "reads": "validate_task fields; counts from patch file paths"}) + "\n")
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
