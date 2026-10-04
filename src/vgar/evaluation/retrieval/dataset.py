"""Pinned HF snapshot, deterministic pilot manifest and bounded source-only Git cache."""
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


def select_tasks(rows, count=25):
    if count < 1:
        raise ValueError("Task count must be positive")
    groups, excluded, seen = defaultdict(list), [], set()
    for row in rows:
        validate_task(row)
        if row["instance_id"] in seen:
            raise ValueError("Duplicate instance ID")
        seen.add(row["instance_id"])
        try:
            paths = changed_source_files(row["patch"])
        except ValueError as exc:
            excluded.append({"instance_id": row["instance_id"], "reason": str(exc)})
            continue
        if len(paths) < 2:
            excluded.append({"instance_id": row["instance_id"], "reason": "fewer_than_two_source_python_files"})
            continue
        groups[row["repo"]].append(row)
    for values in groups.values():
        values.sort(key=lambda r: r["instance_id"])
    selected, position = [], 0
    eligible = sum(map(len, groups.values()))
    if eligible < count:
        raise ValueError(f"Only {eligible} eligible tasks; requested {count}")
    while len(selected) < count:
        for repo in sorted(groups):
            if position < len(groups[repo]) and len(selected) < count:
                selected.append(groups[repo][position])
        position += 1
    return selected, {"raw_count": len(seen), "eligible_count": eligible, "excluded": excluded,
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


def prepare_dataset(root, count=25, dataset_id="princeton-nlp/SWE-bench_Verified", revision=None):
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
    selected, audit = select_tasks(rows, count)
    tasks = []
    for row in selected:
        patch_path = root / "data" / "gold" / "patches" / f"{row['instance_id']}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(row["patch"], encoding="utf-8", newline="\n")
        tasks.append({k: row[k] for k in ("instance_id", "repo", "base_commit", "problem_statement", "difficulty") if k in row} | {
            "query_hash": sha256(row["problem_statement"]), "patch_hash": sha256(row["patch"]),
            "gold_patch_path": patch_path.relative_to(root).as_posix(), "changed_source_files": changed_source_files(row["patch"])})
    manifest = {"dataset_id": dataset_id, "dataset_revision": resolved, "split": "test", "purpose": "initial_retrieval_pilot_not_final_blind",
                "provisional_m3_alignment": True, "query_policy": "problem_statement_only_no_hints_or_gold", "target_count": count,
                "downloads": downloads, "selection_audit": audit, "tasks": tasks}
    destination = root / "data" / "manifests" / f"verified-{resolved[:12]}-{count}.json"
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
