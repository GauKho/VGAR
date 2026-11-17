"""G1 label kit (spec 2026-11-16): sample call sites and non-call name uses from the dev repositories into blind sheets.

  python scripts/g1_label_kit.py --root ~/rt1 --manifest ~/rt1/data/manifests/w10-dev-50-gold.json --out ~/rt1/g1
  python scripts/g1_label_kit.py --out ~/rt1/g1 --lock      # after the sheets are filled

The kit never builds a graph. Trees are the ones R1 extracts under ``<root>/data/repositories/trees``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.g1_labels import (
    agreement_ids,
    item_from_dict,
    item_to_dict,
    lock,
    read_sheet,
    sample_items,
    scan_repository,
    sha256_file,
    write_agreement_sheet,
    write_items_md,
    write_sheet,
)
from vgar.evaluation.retrieval.dataset import read_repository_sources
from vgar.evaluation.retrieval.graph_arm import extract_python_tree


def select_tasks(rows: list[dict]) -> list[dict]:
    """The first task of each repository, in manifest order."""
    seen, chosen = set(), []
    for row in rows:
        if row["repo"] not in seen:
            seen.add(row["repo"])
            chosen.append(row)
    return chosen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--calls", type=int, default=150)
    parser.add_argument("--names", type=int, default=150)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--lock", action="store_true", help="validate the filled sheets and record their hashes")
    args = parser.parse_args(argv)
    out = args.out
    if args.lock:
        items = {k: item_from_dict(v) for k, v in json.loads((out / "items.json").read_text(encoding="utf-8")).items()}
        lock(out, items)
        for entry in json.loads((out / "manifest.json").read_text(encoding="utf-8"))["locks"][-2:]:
            print(entry["sheet"], entry["sha256"])
        return 0
    if args.root is None or args.manifest is None:
        parser.error("--root and --manifest are required unless --lock")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    all_items, tasks, stats, trees = [], [], {}, {}
    for row in select_tasks(manifest["tasks"]):
        _, provenance = read_repository_sources(row, args.root / "data" / "repositories", network=not args.offline)
        key = f"{row['repo'].replace('/', '__')}-{row['base_commit']}"
        tree = args.root / "data" / "repositories" / "trees" / key
        extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
        items, stats[row["repo"]] = scan_repository(tree, repo=row["repo"], task_id=row["instance_id"])
        all_items += items
        trees[row["instance_id"]] = tree
        tasks.append({"task_id": row["instance_id"], "repo": row["repo"], "base_commit": row["base_commit"],
                      "archive": provenance["cache_path"], "archive_sha256": sha256_file(Path(provenance["cache_path"])),
                      "tree": str(tree)})
    calls = sample_items(all_items, "call", args.calls, args.seed)
    names = sample_items(all_items, "name", args.names, args.seed)
    call_ids, name_ids = write_sheet(out / "calls.csv", calls, "C"), write_sheet(out / "name_uses.csv", names, "N")
    rows = list(zip(call_ids, calls)) + list(zip(name_ids, names))
    write_items_md(out / "items.md", rows, trees)
    (out / "items.json").write_text(json.dumps({i: item_to_dict(it) for i, it in rows}, ensure_ascii=False), encoding="utf-8")
    chosen = agreement_ids(call_ids, name_ids)
    write_agreement_sheet(out / "agreement_user.csv", {**read_sheet(out / "calls.csv"), **read_sheet(out / "name_uses.csv")}, chosen)
    (out / "manifest.json").write_text(json.dumps({
        "manifest": str(args.manifest), "manifest_hash": manifest.get("manifest_hash"), "seed": args.seed, "tasks": tasks,
        "stats": stats, "agreement_ids": sorted(chosen), "locks": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    for repo, stat in stats.items():
        print(repo, {k: v if k != "unparsed_files" else len(v) for k, v in stat.items()})
    print(out / "calls.csv", len(calls), out / "name_uses.csv", len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
