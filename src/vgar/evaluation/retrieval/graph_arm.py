"""Graph arm, M2 side: M1 ``RetrievalResult.candidates`` -> RankRecord -> the SAME two-mode scoring as BM25.

Stdlib + sibling M2 modules only (no import of vgar.graph / pydantic): M1 objects are injected as plain dicts by
``scripts/run_graph_retrieval.py``, so this module is unit-testable without tree-sitter/jedi.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any, Callable, Mapping

from .chunks import normalize_path
from .evidence import sha256
from .gold_labels import extract_gold
from .scoring import CorpusIndex, flat_metrics, graph_rank, score_record

TOP_DETAIL = 100
MAX_PY_BYTES = 2_000_000
MAX_PY_FILES = 50_000
TREE_MARKER = ".vgar_tree.json"
ARMS = {"graph": False, "graph_f2p": True}          # arm name -> uses FAIL_TO_PASS?


def corpus_fingerprint(sources: Mapping[str, str]) -> str:
    """Identical to the BM25 runner's ``corpus_hash`` so the comparison can verify both arms saw the same corpus."""
    return sha256(json.dumps({path: sha256(source) for path, source in sorted(sources.items())}, sort_keys=True))


def extract_python_tree(archive_path, repo: str, commit: str, destination) -> dict[str, Any]:
    """Extract EVERY .py (tests included, they are graph traversal material) from the pinned codeload archive.
    Bytes are written untouched so M1 byte offsets match what it hashed. Idempotent; atomic via a .partial dir."""
    destination = Path(destination)
    marker = destination / TREE_MARKER
    if marker.exists():
        meta = json.loads(marker.read_text(encoding="utf-8"))
        if meta.get("commit") != commit or meta.get("repo") != repo:
            raise ValueError("Cached source tree belongs to a different repo/commit")
        return meta
    partial = destination.with_name(destination.name + ".partial")
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    prefix = repo.split("/")[-1] + "-" + commit + "/"
    files: dict[str, str] = {}
    skipped: list[dict[str, str]] = []
    with tarfile.open(archive_path, "r|gz") as bundle:
        for member in bundle:
            if member.isdir() and member.name.rstrip("/") == prefix.rstrip("/"):
                continue
            if not member.name.startswith(prefix):
                raise ValueError("Archive root does not match pinned repository/commit")
            if not member.isfile():
                continue
            rel = normalize_path(member.name[len(prefix):])
            if not rel.endswith(".py"):
                continue
            if member.size > MAX_PY_BYTES:
                skipped.append({"path": rel, "reason": "file_over_2MB"})
                continue
            if len(files) >= MAX_PY_FILES:
                raise ValueError("Archive has too many Python files")
            data = bundle.extractfile(member).read()
            target = partial / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[rel] = hashlib.sha256(data).hexdigest()
    if not files:
        raise ValueError("Archive contains no Python files")
    meta = {"repo": repo, "commit": commit, "python_file_count": len(files), "skipped": skipped,
            "tree_hash": sha256(json.dumps(files, sort_keys=True))}
    (partial / TREE_MARKER).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    partial.rename(destination)
    return meta


def load_fail_to_pass(root, manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    """FAIL_TO_PASS per task from the pinned parquet snapshot already downloaded by ``prepare_manifest``.
    The manifest (and therefore the BM25 baseline binding) is NOT modified."""
    import pyarrow.parquet as parquet
    directory = Path(root) / "data" / "downloads" / manifest["dataset_revision"]
    wanted = {task["instance_id"] for task in manifest["tasks"]}
    found: dict[str, list[str]] = {}
    for path in sorted(directory.glob("test-*.parquet")):
        table = parquet.read_table(path, columns=["instance_id", "FAIL_TO_PASS"])
        for instance_id, raw in zip(table.column("instance_id").to_pylist(), table.column("FAIL_TO_PASS").to_pylist()):
            if instance_id not in wanted:
                continue
            value = json.loads(raw) if isinstance(raw, str) else list(raw)
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                raise ValueError(f"Malformed FAIL_TO_PASS for {instance_id}")
            found[instance_id] = value
    missing = sorted(wanted - set(found))
    if missing:
        raise ValueError(f"FAIL_TO_PASS not found in snapshot {directory} for: {missing[:5]}")
    return found


def evaluate_graph_task(task: Mapping[str, Any], sources: Mapping[str, str], corpus: CorpusIndex,
                        nodes: Mapping[str, Mapping[str, Any]], arm_outputs: Mapping[str, Mapping[str, Any]], *,
                        budget_tokens: int, counter: Callable[[str], int], counter_label: str,
                        max_snippet_lines: int | None = 80) -> dict[str, Any]:
    """``arm_outputs[arm]`` = {"candidates": RetrievalResult.candidates, "anchors": [{"node_id",...}],
    "seconds": float, "diagnostics": {...}}.  Ranking is frozen (rank_hash) BEFORE the developer patch is opened."""
    records = {arm: graph_rank(task["instance_id"], out["candidates"], nodes, sources, corpus, arm=arm)
               for arm, out in arm_outputs.items()}
    frozen = {arm: record.rank_hash for arm, record in records.items()}
    gold = extract_gold(task["patch"], sources)
    arms: dict[str, Any] = {}
    for arm, record in records.items():
        out = arm_outputs[arm]
        scored = score_record(record, gold, budget_tokens=budget_tokens, counter=counter, counter_label=counter_label,
                              max_snippet_lines=max_snippet_lines)
        if scored["rank_hash"] != frozen[arm]:
            raise RuntimeError("Ranking changed after gold extraction")
        metrics = flat_metrics(scored)
        metrics.update(anchor_count=len(out["anchors"]), no_anchors=int(not out["anchors"]),
                       candidates_in=len(out["candidates"]), retrieve_seconds=out["seconds"],
                       mapping_coverage=gold["mapping_coverage"],
                       file_retrievability_coverage=gold["file_retrievability_coverage"])
        detail = record.to_json()
        arms[arm] = {"rank_hash": frozen[arm], "ranking_total_count": len(record.items), "ranked": detail["items"][:TOP_DETAIL],
                     "rank_order": [item.item_id for item in record.items], "anchors": list(out["anchors"]),
                     "unmapped": record.unmapped, "excluded": record.excluded, "diagnostics": out.get("diagnostics", {}),
                     "scoring": scored, "metrics": metrics}
    return {"instance_id": task["instance_id"], "repository": task["repo"], "base_commit": task["base_commit"],
            "status": "SUCCEEDED", "query_hash": sha256(task["problem_statement"]), "patch_hash": sha256(task["patch"]),
            "corpus_hash": corpus_fingerprint(sources), "gold": gold, "arms": arms}
