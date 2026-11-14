"""L4-7 labelling kit: sample commits from the R1 task repositories and write the labelling sheet.

Commits come from first-parent windows that end at each task's ``base_commit`` (never after it).
Merges, commits with no changed ``.py`` file and commits with more than 10 are excluded. The sample is
stratified by changed ``.py`` count (1, 2-3, 4-10) and 60-70% of it has a fix-like subject. One row per
raw-diff baseline entity in production code; GraphDiff's predictions are not in the sheet. The split
into development (40%) and evaluation (60%) is by commit and is made before anyone labels.

The R1 runner reads archives without history, so the repositories must be cloned with full history
under ``--git-root`` as ``<owner>__<name>`` (see docs/status/graphdiff_labelling_guide.md).

Usage:
    python scripts/graphdiff_label_kit.py --manifest <R1 manifest.json> --git-root <clones> --out <dir>
        [--window 50] [--target 100] [--seed 0]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.graph.ast_diff import read_python_blobs
from vgar.graph.graphdiff import SnapshotIndex, entity_source, raw_diff_entities
from vgar.graph.history import CommitChange, CommitHistory, read_commit_history

COLUMNS = ["row_id", "split", "repo", "commit", "subject", "path", "entity", "node_id", "before_code", "after_code",
           "diff_link", "label", "annotator", "note"]
FIX_SUBJECT = re.compile(r"\b(fix|bug|issue|error)", re.IGNORECASE)
STRATA = ("1", "2-3", "4-10")
MAX_CELL = 4000


def _py_count(commit: CommitChange) -> int:
    return len({version.path for change in commit.files for version in (change.before, change.after)
                if version is not None and version.path.endswith(".py")})


def _stratum(count: int) -> str:
    return "1" if count == 1 else ("2-3" if count <= 3 else "4-10")


def _draw(pool: list[dict[str, Any]], quota: int, rng: random.Random) -> list[dict[str, Any]]:
    """Round-robin over strata (each shuffled) until ``quota`` or the pool runs out."""
    groups = {name: [row for row in pool if row["stratum"] == name] for name in STRATA}
    for rows in groups.values():
        rng.shuffle(rows)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < quota and any(groups.values()):
        for name in STRATA:
            if groups[name] and len(chosen) < quota:
                chosen.append(groups[name].pop())
    return chosen


def sample_commits(windows: Mapping[str, Sequence[CommitHistory]], *, target: int = 100,
                   fix_share: tuple[float, float] = (0.6, 0.7), seed: int = 0) -> list[dict[str, Any]]:
    """Seeded, stratified commit sample with its development/evaluation split.

    Args:
        windows: Repository name -> first-parent windows (one per task; shared commits count once).
        target: Number of commits.
        fix_share: Bounds for the share of fix-like subjects; the midpoint is aimed at.
        seed: Random seed.
    """
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for repo in sorted(windows):
        for history in windows[repo]:
            for commit in history.commits:
                count = _py_count(commit)
                if len(commit.parent_ids) > 1 or not 1 <= count <= 10:
                    continue
                candidates.setdefault((repo, commit.commit_id), {
                    "repo": repo, "commit": commit.commit_id, "subject": commit.subject, "py_files": count,
                    "stratum": _stratum(count), "is_fix": bool(FIX_SUBJECT.search(commit.subject))})
    pool = [candidates[key] for key in sorted(candidates)]
    rng = random.Random(seed)
    fix_quota = round(target * (fix_share[0] + fix_share[1]) / 2)
    chosen = _draw([row for row in pool if row["is_fix"]], fix_quota, rng)
    chosen += _draw([row for row in pool if not row["is_fix"]], target - len(chosen), rng)
    if len(chosen) < target:  # not enough non-fix commits: fill with the remaining fix commits
        taken = {(row["repo"], row["commit"]) for row in chosen}
        chosen += _draw([row for row in pool if row["is_fix"] and (row["repo"], row["commit"]) not in taken],
                        target - len(chosen), rng)
    chosen.sort(key=lambda row: (row["repo"], row["commit"]))
    order = list(range(len(chosen)))
    rng.shuffle(order)
    dev = set(order[:round(0.4 * len(chosen))])
    return [dict(row, split="dev" if number in dev else "eval") for number, row in enumerate(chosen)]


def windows_from_manifest(manifest: Mapping[str, Any], git_root: Path, *, window: int
                          ) -> tuple[dict[str, list[CommitHistory]], list[dict[str, str]]]:
    """Read one window per task from the local clones; missing clones and commits are reported.

    Args:
        manifest: R1 gold manifest (``tasks`` with ``repo`` and ``base_commit``).
        git_root: Folder of clones named ``<owner>__<name>``.
        window: Commits per window.
    """
    windows: dict[str, list[CommitHistory]] = {}
    skipped: list[dict[str, str]] = []
    for task in manifest["tasks"]:
        clone = git_root / task["repo"].replace("/", "__")
        if not clone.is_dir():
            skipped.append({"instance_id": task["instance_id"], "reason": f"clone missing: {clone}"})
            continue
        try:
            history = read_commit_history(clone, revision=task["base_commit"], max_commits=window)
        except (ValueError, TypeError) as error:
            skipped.append({"instance_id": task["instance_id"], "reason": f"history unavailable: {error}"})
            continue
        windows.setdefault(task["repo"], []).append(history)
    return windows, skipped


def _index(repo: str, revision: str) -> SnapshotIndex:
    # Node ids follow the R1 graph scheme (repo_key owner__name, source root "src"); no snapshot is needed.
    key = repo.replace("/", "__")
    return SnapshotIndex(key, revision, ("src",), f"{key}-{revision}", {}, frozenset(), {}, {})


def sheet_rows(sample: Sequence[Mapping[str, Any]], git_root: Path) -> list[dict[str, str]]:
    """One row per production-code raw-diff baseline entity of each sampled commit.

    Args:
        sample: ``sample_commits`` rows.
        git_root: Folder of clones named ``<owner>__<name>``.
    """
    rows: list[dict[str, str]] = []
    for item in sample:
        clone = git_root / item["repo"].replace("/", "__")
        commit, = read_commit_history(clone, revision=item["commit"], max_commits=1).commits
        blobs = read_python_blobs(clone, commit)
        for entity in raw_diff_entities(commit, blobs, _index(item["repo"], item["commit"])):
            if entity["in_test_file"]:
                continue
            old, new = blobs[entity["path"]]
            rows.append({
                "row_id": f"{item['commit'][:12]}:{entity['path']}:{entity['entity']}", "split": item["split"],
                "repo": item["repo"], "commit": item["commit"], "subject": item["subject"], "path": entity["path"],
                "entity": entity["entity"], "node_id": entity["node_id"],
                "before_code": entity_source(old, entity["symbol"])[:MAX_CELL],
                "after_code": entity_source(new, entity["symbol"])[:MAX_CELL],
                "diff_link": f"https://github.com/{item['repo']}/commit/{item['commit']}",
                "label": "", "annotator": "", "note": ""})
    return rows


def write_sheet(rows: Sequence[Mapping[str, str]], path: Path) -> None:
    """Write the sheet as CSV (UTF-8 with BOM so spreadsheet programs read it).

    Args:
        rows: ``sheet_rows`` result.
        path: Output file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--git-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--window", type=int, default=50)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    windows, skipped = windows_from_manifest(json.loads(raw), args.git_root, window=args.window)
    sample = sample_commits(windows, target=args.target, seed=args.seed)
    rows = sheet_rows(sample, args.git_root)
    write_sheet(rows, args.out / "sheet.csv")
    record = {"seed": args.seed, "target": args.target, "window": args.window,
              "manifest": str(args.manifest), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "commits": sample, "skipped_tasks": skipped, "rows": len(rows),
              "fix_share": sum(row["is_fix"] for row in sample) / len(sample) if sample else None}
    (args.out / "sample.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"commits": len(sample), "rows": len(rows), "skipped_tasks": len(skipped)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
