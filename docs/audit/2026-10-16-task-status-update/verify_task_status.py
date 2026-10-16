"""Documentation QA only: read saved evidence, never run tests or inference."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
STATUS = ROOT / "Task Status.md"
started = datetime.now(timezone.utc)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(text):
    found = re.findall(
        r"^\| (W\d{2}-\d{2}-(?:CHUNG|M[123]|DOD)-\d{2})\s*\|[^\n]*?\|\s*\*\*(HT|MP|CT|CX)\*\*\s*\|",
        text, re.M,
    )
    assert len(found) == len(dict(found)) == 150, "Missing/duplicate task rows"
    return dict(found)


text = STATUS.read_text(encoding="utf-8")
before = entries((AUDIT / "Task_Status.before.md").read_text(encoding="utf-8"))
current = entries(text)
checklist = load(ROOT / "docs/audit/2026-10-13/plan-checklist.json")
assert set(current) == {row["id"] for row in checklist} == set(before)
changes = {key: {"before": before[key], "after": status}
           for key, status in current.items() if before[key] != status}
allowed = {f"W07-08-M2-{i:02}" for i in range(1, 8)} | {
    "W07-08-DOD-01", "W05-06-CHUNG-03", "W05-06-DOD-01",
}
assert set(changes) == allowed and all(v["after"] == "HT" for v in changes.values())
assert Counter(current.values()) == {"HT": 47, "MP": 48, "CT": 25, "CX": 30}
by_week = {week: dict(Counter(status for key, status in current.items() if key.startswith(week)))
           for week in sorted({key[:6] for key in current})}
for week, counts in by_week.items():
    label = "–".join(str(int(v)) for v in week[1:].split("-"))
    summary = re.search(r"^\| " + re.escape(label) + r"\s*\|([^\n]+)", text, re.M)
    assert summary, week
    assert [int(v.strip()) for v in summary[1].strip(" | ").split("|")] == [
        sum(counts.values()), *[counts.get(v, 0) for v in ("HT", "MP", "CT", "CX")]
    ], week

table_count, width, in_fence = 0, None, False
for number, line in enumerate(text.splitlines(), 1):
    if line.lstrip().startswith("```"):
        in_fence = not in_fence
    if in_fence:
        continue
    if line.startswith("|"):
        columns = re.split(r"(?<!\\)\|", line)[1:-1]
        if width is None:
            table_count += 1
            width = len(columns)
        assert len(columns) == width, f"Malformed table at line {number}"
    else:
        width = None
missing_links = []
links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
for link in links:
    if link.startswith(("https://", "http://", "#", "mailto:")):
        continue
    if not (ROOT / link.split("#")[0].strip("<>")).exists():
        missing_links.append(link)
assert not missing_links, missing_links

m2 = ROOT / "M2_week_7_8"
sys.path.insert(0, str(m2 / "src"))
from vgar_m2_w78.campaign import assess_record  # noqa: E402

final_root = m2 / "results/final_acceptance/2026-10-15-v11-r002"
manifest = load(final_root / "run_manifest.json")
assert manifest["status"] == "PASS" and manifest["runtime_revision"] == "r002"
assert manifest["prompt_version"] == "m2-w78-v11" and manifest["feedback"] is None
assert set(manifest["cases"]) == {"A", "B", "C"}
real_audits = {key: assess_record(final_root / case["record"])
               for key, case in manifest["cases"].items()}
assert all(value["status"] == "PASS" and not value["gate_errors"] for value in real_audits.values())
core = load(m2 / "results/integration-qualification/final-core-suite/20261016T070502676971Z-3cde4ebc98db/run_record.json")
assert core["status"] == "PASS" and "236 passed" in core["stages"]["pytest"]["stdout"]
suite = ET.parse(ROOT / "docs/audit/2026-10-16-m2-w7-w8-integration/final-vgar-suite.xml")
cases = list(suite.iter("testcase"))
counts = Counter("FAIL" if c.find("failure") is not None else "ERROR" if c.find("error") is not None
                 else "SKIP" if c.find("skipped") is not None else "PASS" for c in cases)
assert counts == {"PASS": 571, "SKIP": 2, "FAIL": 1}
retrieval = load(ROOT / "artifacts/m2/w5-w6/final-verification/20261013T125343095888Z-13d9f9501ba3/result.json")
assert retrieval["status"] == "PASS" and retrieval["attempted"] == 25 and retrieval["paired_tasks"] == 22
assert retrieval["owner_signoff"] == "PENDING_M1_OWNER_REVIEW"
assert current["W05-06-M2-04"] == "MP"
assert all(current[f"W07-08-M3-{i:02}"] != "HT" for i in range(1, 5))
relocation = load(m2 / "integration/relocation.json")
assert all(sha(m2 / name) == value["after"] for name, value in relocation["relocated_files"].items())

result = {
    "status": "PASS", "complete": True, "scope": "documentation and saved-evidence QA; no tests/inference rerun",
    "started_utc": started.isoformat(), "ended_utc": datetime.now(timezone.utc).isoformat(),
    "task_status_sha256": sha(STATUS), "before_sha256": sha(AUDIT / "Task_Status.before.md"),
    "task_count": len(current), "counts": dict(Counter(current.values())), "by_week": by_week,
    "changes": changes, "table_count": table_count, "missing_local_links": missing_links,
    "real_saved_audits": real_audits, "core_tests": 236, "vgar_suite": dict(counts),
    "retrieval_attempted": 25, "retrieval_valid_pairs": 22,
    "m1_owner_signoff": retrieval["owner_signoff"], "integration_hashes_match": True,
}
path = AUDIT / "task-status-qa.json"
if path.exists():
    raise FileExistsError("Keep existing QA; record a new version if the document changes")
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("status", "task_count", "counts", "table_count", "missing_local_links")}, ensure_ascii=False))
print(path)
