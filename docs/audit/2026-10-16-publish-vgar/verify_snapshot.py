"""Audit the isolated Git index without printing possible secret values."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
env = os.environ.copy()
env["GIT_INDEX_FILE"] = str(ROOT / ".git/index-publish-vgar-20261016")


def git(*args, **kwargs):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True, check=True, **kwargs).stdout


entries = []
for item in git("ls-files", "--stage", "-z").split(b"\0"):
    if item:
        meta, name = item.split(b"\t", 1)
        mode, oid, stage = meta.decode().split()
        assert stage == "0" and mode in ("100644", "100755"), ("non-regular/unmerged", name.decode())
        entries.append((name.decode("utf-8"), oid))
batch = git("cat-file", "--batch", input=("\n".join(oid for _, oid in entries)+"\n").encode())
blobs = {}
offset = 0
for path, oid in entries:
    end = batch.index(b"\n", offset)
    actual_oid, kind, size = batch[offset:end].decode().split()
    assert actual_oid == oid and kind == "blob"
    size = int(size)
    raw = batch[end + 1:end + 1 + size]
    assert len(raw) == size and batch[end + 1 + size:end + 2 + size] == b"\n"
    offset = end + 2 + size
    assert size < 95 * 1024 * 1024, ("oversized GitHub blob", path, size)
    assert not any(part in (".git", ".venv", ".venv-m2-w5-w6", "node_modules", "__pycache__", ".workspaces") for part in Path(path).parts), ("runtime/cache", path)
    assert Path(path).name != ".env" and not Path(path).name.startswith(".env.") or Path(path).name == ".env.example", ("environment file", path)
    assert not path.endswith((".safetensors", ".bin", ".pyc", ".pyo")), ("model/cache file", path)
    blobs[path] = raw

patterns = {
    "huggingface_token": rb"\bhf_[A-Za-z0-9]{25,}\b",
    "github_classic_token": rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    "github_fine_grained_token": rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    "openai_style_token": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b",
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "aws_access_key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "url_credential": rb"https?://[^/\s:@]+:[^/\s@]{8,}@github\.com",
}
findings = []
for path, raw in blobs.items():
    for kind, pattern in patterns.items():
        for match in re.finditer(pattern, raw):
            findings.append({"path": path, "line": raw[:match.start()].count(b"\n")+1, "kind": kind})
assert not findings, json.dumps({"potential_secrets": findings}, ensure_ascii=False)
pin = json.loads((ROOT / "M2_week_7_8/config/source_pin.json").read_text())
for path, expected in pin["hashes"].items():
    assert hashlib.sha256(blobs[path]).hexdigest() == expected, ("staged shared boundary differs", path)
exact = [path for path in blobs if path.startswith(("M2_week_7_8/", "docs/audit/", "artifacts/m2/", "results/retrieval/"))]
for path in exact:
    assert blobs[path] == (ROOT / path).read_bytes(), ("staged normalized frozen artifact", path)
required = (
    "README.md", "requirement.txt", "Task Status.md", "PROGRESS.md", ".gitattributes", "run_m2_abc.ps1",
    "M2_week_7_8/results/b_repair/2026-10-15-evidence-driven-b/frozen_inputs.json",
    "M2_week_7_8/results/b_repair/2026-10-15-evidence-driven-b/revisions/r002.json",
    "M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json",
    "M2_week_7_8/results/manual_abc/20261015T114826234Z-922d5c80/summary.json",
)
assert all(path in blobs for path in required)
source_paths = git("ls-files", "--others", "--exclude-standard", "-z",
                   "--", "M2_week_7_8", "src", "scripts", "tests", "docs", "artifacts/m2").split(b"\0")
assert not source_paths or source_paths == [b""], "Unstaged deliverables remain in isolated index"
main_env = os.environ.copy()
main_env.pop("GIT_INDEX_FILE", None)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, env=main_env, text=True).strip()
assert head == pin["revision"], "Working checkout HEAD changed"
assert subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, env=main_env).returncode == 0, "Original index changed"
report = {
    "status": "PASS", "created_utc": datetime.now(timezone.utc).isoformat(),
    "branch": "feat/vgar-integrated-m2-w7-w8-20261016", "parent": head,
    "staged_tree_files": len(entries), "total_blob_bytes": sum(map(len, blobs.values())),
    "exact_frozen_artifact_files": len(exact), "shared_hashes_verified": len(pin["hashes"]),
    "secret_pattern_findings": findings, "scan_limit": "pattern scan, not a guarantee of absence of every secret",
    "working_head_unchanged": True, "original_index_unchanged": True,
    "largest_files": sorted(({"path": p, "bytes": len(b)} for p, b in blobs.items()), key=lambda r: r["bytes"], reverse=True)[:8],
    "excluded": ["venvs", "weights", "dataset/source caches", "temporary workspaces", "large raw retrieval tasks", "other ignored development campaigns"],
}
output = Path(__file__).parent / ("snapshot-check-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
with output.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({k: report[k] for k in ("status", "staged_tree_files", "total_blob_bytes", "exact_frozen_artifact_files", "shared_hashes_verified", "secret_pattern_findings", "working_head_unchanged", "original_index_unchanged")}))
print(str(output))
