"""M1-W12-2: dry-run toàn chuỗi held-out trên 2 dev task (export -> config -> runner -> harness -> aggregate).

Chạy 2 lần (2 phiên máy khác nhau); cổng "harness ổn định" đạt khi cả hai dry_run.json có gate = PASS.
Chạy model thật, trên máy GPU, do người dùng khởi chạy. Runbook: docs/m1_w12_dry_run_runbook.md.

  ~/vgar/.venv/bin/python scripts/dry_run_heldout_chain.py --template configs/m3/w10_dev_stage1.json \
      --data-root ~/w9 --parquet <parquet đã pin> --out results/m1/w12/dry_run/<timestamp>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.dry_run import Context, run_chain  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", type=Path, default=ROOT / "configs/m3/w10_dev_stage1.json")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arms", default="A0,A1,A2,A3", help="comma-separated; without A3 the gate is INCOMPLETE")
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/m1/w10_dev_manifest.json")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    context = Context(template=args.template.resolve(), data_root=args.data_root.resolve(), out=args.out.resolve(),
                      arms=tuple(a for a in args.arms.split(",") if a), manifest=args.manifest.resolve(),
                      parquet=args.parquet.resolve(), python=args.python)
    record = run_chain(context)
    print(json.dumps({"gate": record["gate"], "infra_errors": len(record["infra_errors"]),
                      "precondition_error": record.get("precondition_error"),
                      "record": str(context.out / "dry_run.json")}, ensure_ascii=False))
    return 0 if record["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
