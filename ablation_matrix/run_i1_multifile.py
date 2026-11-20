"""I1 multi-file (19/11): on multi-file gold patches, does the graph impact of ONE changed file reach the OTHER changed files?

Uses the R1 data layout (archives -> Python tree -> graph, same as run_r1_ablation). Dev only; no LLM, no MCP.

  PYTHONPATH=src python ablation_matrix/run_i1_multifile.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
      --out ~/rt1/results/i1_multifile_dev
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT / "scripts")]

import run_graph_retrieval as runner

from vgar.evaluation.gold_impact import cross_file_reach, filter_patch
from vgar.evaluation.retrieval.dataset import read_repository_sources, require_split
from vgar.evaluation.retrieval.graph_arm import extract_python_tree


def summarize(rows: list[dict]) -> dict:
    """Per changed file (source): share of the other gold files reached, graph vs same-directory baseline."""
    def share(key: str) -> float | None:
        return statistics.mean(len(r[key]) / len(r["others"]) for r in rows) if rows else None

    return {"n_sources": len(rows),
            "graph_reach": share("reached"), "same_dir_reach": share("same_dir_reached"),
            "graph_any": sum(bool(r["reached"]) for r in rows), "same_dir_any": sum(bool(r["same_dir_reached"]) for r in rows),
            "median_graph_region_files": statistics.median(r["region_files"] for r in rows) if rows else None,
            "median_same_dir_files": statistics.median(r["same_dir_files"] for r in rows) if rows else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require_split(manifest, allowed=("dev",), protocol="r1")
    builder_hash = runner.source_fingerprint(ROOT)["digest"]
    tasks, rows = [], []
    for row in (t for t in manifest["tasks"] if len(t["changed_source_files"]) >= 2):
        patch = (root / row["gold_patch_path"]).read_text(encoding="utf-8")
        diff, _ = filter_patch(patch, set(row["changed_source_files"]))
        try:
            _, provenance = read_repository_sources(row, root / "data" / "repositories", network=True)
            tree = root / "data" / "repositories" / "trees" / runner.key_of(row)
            extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
            document, _ = runner.load_or_build_graph(root, row, tree, rebuild=False, builder_hash=builder_hash,
                                                     cache=False)
            reach = cross_file_reach(diff, document, tree)
            tasks.append({"instance_id": row["instance_id"], "status": "OK", "sources": reach})
            rows += reach
        except Exception as error:  # noqa: BLE001 -- every task stays in the record with its reason
            tasks.append({"instance_id": row["instance_id"], "status": "ERROR", "reason": f"{type(error).__name__}: {error}"})
        print(row["instance_id"], tasks[-1]["status"], tasks[-1].get("reason", ""), flush=True)
    record = {"manifest": str(args.manifest), "manifest_hash": manifest.get("manifest_hash"),
              "builder_hash": builder_hash, "summary": summarize(rows), "tasks": tasks}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "i1_multifile.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
