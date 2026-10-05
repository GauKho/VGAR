"""Pinned HF snapshot, deterministic pilot manifest and bounded source-only Git cache."""
import hashlib
import json
import re
import tarfile
import urllib.request
import time
from collections import defaultdict
from pathlib import Path

from .chunks import decode_source, is_source, normalize_path
from .evidence import sha256, write_json
from .gold_labels import parse_patch


# ---- Split policy (decision W5-6): dev 40% / held-out 60%, by hash of instance_id ----
DEV_PERCENT = 40
SPLIT_POLICY = "sha256_instance_id_first8hex_mod100_lt40_dev_v1"
SPLITS = ("dev", "heldout")


def split_of(instance_id, dev_percent=DEV_PERCENT):
    """Deterministic split. Depends only on instance_id: stable across machines, runs and dataset order."""
    bucket = int(hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "dev" if bucket < dev_percent else "heldout"


def require_split(manifest, allowed=("dev",)):
    """Guard: refuse to evaluate a manifest that contains tasks outside the allowed split(s).
    The split is RECOMPUTED from instance_id, so a hand-edited 'split' field cannot bypass it."""
    declared = manifest.get("split")
    if declared not in allowed:
        raise ValueError(f"Manifest split is {declared!r}; allowed {list(allowed)}. Regenerate it with scripts/prepare_manifest.py "
                         "(held-out needs an explicit --allow-heldout and a recorded decision)")
    for task in manifest.get("tasks", []):
        actual = split_of(task["instance_id"])
        if actual not in allowed or task.get("split") != actual:
            raise ValueError(f"Task {task['instance_id']} is {actual!r} (manifest field: {task.get('split')!r}); allowed {list(allowed)}")


def validate_task(row):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", row.get("repo", "")) or any(p in {".", ".."} for p in row["repo"].split("/")):
        raise ValueError("Invalid GitHub repository name")
    if not re.fullmatch(r"[0-9a-f]{40}", row.get("base_commit", "")):
        raise ValueError("base_commit must be pinned 40-character SHA")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", row.get("instance_id", "")):
        raise ValueError("Invalid instance ID")
    if not isinstance(row.get("problem_statement"), str) or not row["problem_statement"].strip():
        raise ValueError("Missing problem_statement")


def changed_source_files(patch):
    return sorted({c["old_path"] or c["new_path"] for c in parse_patch(patch) if is_source(c["old_path"] or c["new_path"] or "")})


def select_tasks(rows, count=25, split="dev", min_source_files=2):
    """Pick `count` tasks from ONE split. Round-robin over repos keeps the pilot diverse.
    min_source_files=2 -> multi-file pilot; min_source_files=1 -> retrieval pool that also contains single-file tasks."""
    if count < 1:
        raise ValueError("Task count must be positive")
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    if min_source_files < 1:
        raise ValueError("min_source_files must be >= 1")
    groups, excluded, seen = defaultdict(list), [], set()
    raw_by_split = {name: 0 for name in SPLITS}
    for row in rows:
        validate_task(row)
        if row["instance_id"] in seen:
            raise ValueError("Duplicate instance ID")
        seen.add(row["instance_id"])
        row_split = split_of(row["instance_id"])
        raw_by_split[row_split] += 1
        if row_split != split:
            continue                       # other split: counted, never inspected further
        try:
            paths = changed_source_files(row["patch"])
        except ValueError as exc:
            excluded.append({"instance_id": row["instance_id"], "reason": str(exc)})
            continue
        if len(paths) < min_source_files:
            excluded.append({"instance_id": row["instance_id"], "reason": f"fewer_than_{min_source_files}_source_python_files"})
            continue
        groups[row["repo"]].append(row)
    for values in groups.values():
        values.sort(key=lambda r: r["instance_id"])
    selected, position = [], 0
    eligible = sum(map(len, groups.values()))
    if eligible < count:
        raise ValueError(f"Only {eligible} eligible {split} tasks; requested {count}")
    while len(selected) < count:
        for repo in sorted(groups):
            if position < len(groups[repo]) and len(selected) < count:
                selected.append(groups[repo][position])
        position += 1
    return selected, {"raw_count": len(seen), "raw_by_split": raw_by_split, "split": split, "min_source_files": min_source_files,
                      "eligible_count": eligible, "excluded": excluded,
                      "selection_policy": "repo_round_robin_then_instance_id_v1", "seed": None,
                      "eligible_by_repo": {k: len(v) for k, v in sorted(groups.items())}}


def download(url, destination, max_bytes=100_000_000):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "M2-retrieval-pilot/0.1"}), timeout=60) as response, temporary.open("wb") as output:
            size = 0
            while data := response.read(1024 * 1024):
                size += len(data)
                if size > max_bytes or time.perf_counter() - started > 180:
                    raise ValueError("Download exceeds bounded size")
                output.write(data)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_dataset(root, count=25, dataset_id="princeton-nlp/SWE-bench_Verified", revision=None, split="dev", min_source_files=2):
    import pyarrow.parquet as parquet
    root = Path(root)
    if dataset_id not in {"princeton-nlp/SWE-bench_Verified", "SWE-bench/SWE-bench_Verified"}:
        raise ValueError("Only official SWE-bench Verified repositories supported")
    if revision is not None and not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Dataset revision must be 40-character SHA")
    metadata_url = f"https://huggingface.co/api/datasets/{dataset_id}" + (f"/revision/{revision}" if revision else "")
    with urllib.request.urlopen(metadata_url, timeout=60) as response:
        metadata = json.load(response)
    resolved = metadata["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", resolved) or revision and resolved != revision:
        raise ValueError("Dataset revision mismatch")
    snapshot = root / "data" / "downloads" / resolved
    write_json(snapshot / "hf_metadata.json", metadata)
    paths = sorted(s["rfilename"] for s in metadata["siblings"] if re.fullmatch(r"data/test-\d+-of-\d+\.parquet", s["rfilename"]))
    if not paths:
        raise ValueError("No test parquet in pinned snapshot")
    rows, downloads = [], []
    for path in paths:
        local = snapshot / Path(path).name
        if not local.exists():
            download(f"https://huggingface.co/datasets/{dataset_id}/resolve/{resolved}/{path}", local)
        downloads.append({"path": str(local.relative_to(root)), "hash": sha256(local.read_bytes())})
        for batch in parquet.ParquetFile(local).iter_batches(batch_size=64):
            rows.extend(batch.to_pylist())
    selected, audit = select_tasks(rows, count, split=split, min_source_files=min_source_files)
    tasks = []
    for row in selected:
        patch_path = root / "data" / "gold" / "patches" / f"{row['instance_id']}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(row["patch"], encoding="utf-8", newline="\n")
        tasks.append({k: row[k] for k in ("instance_id", "repo", "base_commit", "problem_statement", "difficulty") if k in row} | {
            "query_hash": sha256(row["problem_statement"]), "patch_hash": sha256(row["patch"]),
            "gold_patch_path": patch_path.relative_to(root).as_posix(), "changed_source_files": changed_source_files(row["patch"]),
            "split": split_of(row["instance_id"]), "is_multi_file": len(changed_source_files(row["patch"])) >= 2})
    purpose = "retrieval_dev_tuning_allowed" if split == "dev" else "FINAL_HELDOUT_no_tuning_after_viewing"
    manifest = {"dataset_id": dataset_id, "dataset_revision": resolved, "split": split, "purpose": purpose,
                "split_policy": {"name": SPLIT_POLICY, "dev_percent": DEV_PERCENT}, "min_source_files": min_source_files,
                "provisional_m3_alignment": True, "query_policy": "problem_statement_only_no_hints_or_gold", "target_count": count,
                "downloads": downloads, "selection_audit": audit, "tasks": tasks}
    destination = root / "data" / "manifests" / f"verified-{resolved[:12]}-{split}-{count}.json"
    # Locked manifest: rerunning with same pinned input cannot replace a different selection.
    if destination.exists() and json.loads(destination.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Existing locked manifest differs; choose a new experiment manifest")
    write_json(destination, manifest)
    return destination, manifest


def read_archive_sources(archive_path, repo, commit):
    prefix = repo.split("/")[-1] + "-" + commit + "/"
    sources, excluded = {}, []
    with tarfile.open(archive_path, "r|gz") as bundle:
        for member in bundle:
            if member.isdir() and member.name.rstrip("/") == prefix.rstrip("/"):
                continue
            if not member.name.startswith(prefix):
                raise ValueError("Archive root does not match pinned repository/commit")
            path = normalize_path(member.name[len(prefix):])
            if not member.isfile() or not is_source(path):
                continue
            if member.size > 2_000_000:
                excluded.append({"path": path, "reason": "file_over_2MB"})
                continue
            if len(sources) >= 50_000:
                raise ValueError("Archive has too many source files")
            try:
                sources[path] = decode_source(bundle.extractfile(member).read())
            except (SyntaxError, UnicodeError) as exc:
                excluded.append({"path": path, "reason": "decode_error", "message": str(exc)})
    if not sources:
        raise ValueError("Archive contains no eligible Python source")
    return sources, {"source_backend": "github_codeload_commit_archive", "snapshot_commit": commit,
                     "commit_validation": "immutable_40_SHA_URL_and_archive_root; not_git_object_hash_validation",
                     "source_file_count": len(sources), "source_bytes": sum(len(s.encode("utf-8")) for s in sources.values()),
                     "excluded_sources": excluded}


def read_repository_sources(row, cache_root, network=True):
    validate_task(row)
    cache_root = Path(cache_root)
    # No checkout and no Git fetch process: streaming archive avoids pack/history/auth hangs.
    archive = cache_root / "archives" / f"{row['repo'].replace('/', '__')}-{row['base_commit']}.tar.gz"
    sidecar = archive.with_suffix(".json")
    url = f"https://codeload.github.com/{row['repo']}/tar.gz/{row['base_commit']}"
    if not archive.exists():
        if not network:
            raise RuntimeError(f"Missing archive for {row['instance_id']}; run once with network")
        download(url, archive, max_bytes=300_000_000)
        write_json(sidecar, {"url": url, "archive_hash": sha256(archive.read_bytes()), "base_commit": row["base_commit"]})
    if not sidecar.exists():
        raise ValueError("Archive cache has no provenance sidecar")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    if metadata["url"] != url or metadata["base_commit"] != row["base_commit"] or metadata["archive_hash"] != sha256(archive.read_bytes()):
        raise ValueError("Archive hash/provenance mismatch")
    sources, provenance = read_archive_sources(archive, row["repo"], row["base_commit"])
    provenance.update(metadata, cache_path=str(archive))
    return sources, provenance
