"""M1-X2 (RQ3): bảng I1, graph impact vs diff-only trên gold patch -> <out>/i1.json + <out>/i1.md. Chỉ dev.

  python scripts/measure_patch_impact.py --manifest configs/m1/w10_dev_manifest.json --data-root ~/w9 \
      --parquet <parquet đã pin> --task-inputs configs/m3/w10_dev/tasks --out results/m1/w12/i1/<timestamp>

Checkout của mỗi task: <data-root>/repositories/<instance_id> (base commit, không áp test_patch).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.gold_impact import evaluate_task, render_i1, summarize  # noqa: E402
from vgar.evaluation.incremental_bench import environment_info  # noqa: E402
from vgar.evaluation.retrieval.dataset import require_split  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--task-inputs", type=Path, required=True, help="directory of <instance_id>.json task inputs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="only the first N manifest tasks")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        require_split(manifest, allowed=("dev",))
    except ValueError as error:
        parser.exit(2, f"{parser.prog}: error: {error}\n")
    import pyarrow.parquet as pq

    tasks = manifest["tasks"][: args.limit] if args.limit else manifest["tasks"]
    wanted = {t["instance_id"] for t in tasks}
    rows = {r["instance_id"]: r for r in pq.read_table(args.parquet).to_pylist() if r["instance_id"] in wanted}
    results = []
    for task in tasks:
        task_id = task["instance_id"]
        inputs = args.task_inputs / f"{task_id}.json"
        if not inputs.exists():
            results.append({"task_id": task_id, "status": "EXCLUDED", "reason": f"no task input {inputs.name}"})
        elif task_id not in rows:
            results.append({"task_id": task_id, "status": "ERROR", "reason": "task missing from parquet"})
        else:
            roots = json.loads(inputs.read_text(encoding="utf-8"))["source_roots"]
            results.append(evaluate_task(task_id, args.data_root / "repositories" / task_id, roots, rows[task_id]))
        print(task_id, results[-1]["status"], results[-1].get("reason", ""), flush=True)
    summary = summarize(results)
    record = {"manifest": str(args.manifest), "manifest_hash": manifest.get("manifest_hash"),
              "parquet": str(args.parquet), "environment": environment_info(ROOT), "summary": summary,
              "tasks": results}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "i1.json").write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    (args.out / "i1.md").write_text(render_i1(summary), encoding="utf-8")
    print(args.out / "i1.json")
    print(args.out / "i1.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
