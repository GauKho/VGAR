"""Add gold patches to a dev manifest that has none (RT-1 spec §5).

``configs/m1/w10_dev_manifest.json`` lists 50 dev tasks but no gold patch,
which ``run_graph_retrieval.py`` needs. This reads the pinned SWE-bench
Verified parquet, checks it is the one the manifest names, and writes:

- ``<root>/data/gold/patches/<instance_id>.patch``
- ``<root>/data/downloads/<dataset_revision>/<parquet name>`` (read by ``load_fail_to_pass``)
- ``<root>/data/manifests/w10-dev-50-gold.json``: the same tasks plus ``patch_hash``,
  ``gold_patch_path``, ``changed_source_files``, ``is_multi_file`` and ``source_manifest_hash``.

Usage:
    python scripts/materialize_dev_gold.py configs/m1/w10_dev_manifest.json <parquet> <root>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.retrieval.dataset import (
    changed_source_files,
    split_of,
    validate_task,
)

OUTPUT_NAME = "w10-dev-50-gold.json"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def materialize(manifest: Path, parquet: Path, root: Path) -> Path:
    """Write gold patches and a gold-bearing copy of ``manifest``; return the new manifest path.

    Args:
        manifest: Dev manifest with ``parquet_hash``, ``dataset_revision`` and tasks carrying ``query_hash``.
        parquet: Local copy of the pinned SWE-bench Verified test parquet.
        root: Evaluation root; ``data/`` is created under it.
    """
    import pyarrow.parquet as pq
    source = json.loads(manifest.read_text(encoding="utf-8"))
    if source.get("split") != "dev":
        raise ValueError("only a dev manifest can be materialized")
    if _sha(parquet.read_bytes()) != source["parquet_hash"]:
        raise ValueError(f"parquet hash differs from the manifest's parquet_hash: {parquet}")
    wanted = {task["instance_id"] for task in source["tasks"]}
    rows = {row["instance_id"]: row for row in pq.read_table(parquet).to_pylist() if row["instance_id"] in wanted}
    missing = sorted(wanted - set(rows))
    if missing:
        raise ValueError(f"tasks missing from parquet: {missing}")
    tasks = []
    for task in source["tasks"]:
        validate_task(task)
        row = rows[task["instance_id"]]
        if split_of(task["instance_id"]) != "dev" or task.get("split") != "dev":
            raise ValueError(f"{task['instance_id']} is not a dev task")
        if _sha(row["problem_statement"].encode("utf-8")) != task["query_hash"]:
            raise ValueError(f"query_hash mismatch for {task['instance_id']}")
        if row["base_commit"] != task["base_commit"] or row["repo"] != task["repo"]:
            raise ValueError(f"repo/base_commit mismatch for {task['instance_id']}")
        patch_path = root / "data" / "gold" / "patches" / f"{task['instance_id']}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(row["patch"], encoding="utf-8", newline="\n")
        changed = changed_source_files(row["patch"])
        tasks.append({**task, "patch_hash": _sha(row["patch"].encode("utf-8")),
                      "gold_patch_path": patch_path.relative_to(root).as_posix(),
                      "changed_source_files": changed, "is_multi_file": len(changed) >= 2})
    downloads = root / "data" / "downloads" / source["dataset_revision"]
    downloads.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(parquet, downloads / parquet.name)
    output = root / "data" / "manifests" / OUTPUT_NAME
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {**{key: value for key, value in source.items() if key != "tasks"},
                "source_manifest_hash": source["manifest_hash"], "tasks": tasks}
    output.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    output = materialize(args.manifest, args.parquet, args.root.resolve())
    tasks = json.loads(output.read_text(encoding="utf-8"))["tasks"]
    print(f"{len(tasks)} tasks -> {output} (multi-file: {sum(t['is_multi_file'] for t in tasks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
