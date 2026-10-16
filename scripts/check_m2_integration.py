"""Verify M2 copy/preservation without re-copying, importing M2 or running models."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audit/2026-10-16-m2-w7-w8-integration"


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compare_files(root: Path, expected: dict) -> dict:
    changed, missing = [], []
    def check(item):
        name, metadata = item
        path = root / name
        if not path.is_file():
            return "missing", name
        if path.is_symlink() or file_hash(path) != metadata["sha256"]:
            return "changed", name
        return None, name
    # Bounded parallel reads avoid thousands of serialized Windows file opens.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for state, name in pool.map(check, expected.items()):
            if state == "missing":
                missing.append(name)
            elif state == "changed":
                changed.append(name)
    return {"changed": sorted(changed), "missing": sorted(missing)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("copy", "final"), required=True)
    args = parser.parse_args(argv)
    start, timer = datetime.now(timezone.utc), time.monotonic()
    before = json.loads((AUDIT / "before.json").read_text(encoding="utf-8"))
    source = Path(before["source_root"])
    embedded = ROOT / "M2_week_7_8"
    if Path(before["destination"]).resolve() != embedded.resolve():
        raise ValueError("Snapshot belongs to another destination")
    expected = before["source_files"]
    original = compare_files(source, expected)
    source_extra = sorted({p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} - set(expected))
    relocated = {}
    if args.stage == "final":
        receipt = json.loads((embedded / "integration/relocation.json").read_text(encoding="utf-8"))
        relocated = receipt["relocated_files"]
    copy_expected = dict(expected)
    backup_errors = []
    for name, metadata in relocated.items():
        if metadata["before"] != expected[name]["sha256"]:
            backup_errors.append(name + ": original hash not bound to snapshot")
        backup = embedded / "integration/originals" / name
        if not backup.is_file() or file_hash(backup) != expected[name]["sha256"]:
            backup_errors.append(name + ": original backup differs")
        copy_expected[name] = {"sha256": metadata["after"]}
    copied = compare_files(embedded, copy_expected)
    missing_dirs = [p for p in before["source_directories"] if not (embedded / p).is_dir()]
    vgar = {p: {"sha256": h} for p, h in before["vgar_existing_files"].items()}
    # These files belong to this integration; all other pre-existing files are protected.
    owned = {
        "README.md", "PROGRESS.md", "run_m2_abc.ps1", "tests/m2/test_w78_integration.py",
        "docs/handoff/M2_W7_W8_INTEGRATION_2026-10-16.md",
        "docs/superpowers/plans/2026-10-16-integrate-m2-w7-w8-standalone.md",
        ".superpowers/sdd/2026-10-16-integrate-m2-w7-w8-standalone/progress.md",
    }
    protected = compare_files(ROOT, {p: v for p, v in vgar.items() if p not in owned})
    errors = original["changed"] + original["missing"] + source_extra + copied["changed"] + copied["missing"] + missing_dirs + backup_errors + protected["changed"] + protected["missing"]
    result = {
        "status": "FAIL" if errors else "PASS", "stage": args.stage,
        "source_root": str(source), "destination": str(embedded),
        "copied_files": len(expected), "copied_directories": len(before["source_directories"]),
        "bytes": sum(v["size"] for v in expected.values()),
        "copy_mismatches": copied["changed"] + copied["missing"] + missing_dirs,
        "original_source": original, "source_added_files": source_extra,
        "protected_vgar": protected, "backup_errors": backup_errors,
        "started_utc": start.isoformat(), "ended_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": time.monotonic() - timer,
    }
    path = AUDIT / ("copy.json" if args.stage == "copy" else f"preservation-{start:%Y%m%dT%H%M%S%fZ}.json")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
