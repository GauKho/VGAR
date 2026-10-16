"""Record this audit's inventory and plan checklist; never imports product code.

Usage: python docs/audit/2026-10-13/audit_snapshot.py --plan PATH
Outputs only inside this audit directory. Does not run models, edit source,
modify Git, install packages, or equate file existence with completion.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def write_json(name: str, value: object) -> None:
    (OUTPUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    tracked = git("ls-files").splitlines()
    inventory = []
    for relative in tracked:
        path = ROOT / relative
        entry = {"path": relative, "exists": path.is_file()}
        if path.is_file():
            data = path.read_bytes()
            entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if path.suffix == ".py":
                try:
                    source = data.decode("utf-8-sig")
                    tree = ast.parse(source, filename=relative)
                    entry["lines"] = len(source.splitlines())
                    entry["definitions"] = [
                        {"type": type(node).__name__, "name": node.name,
                         "line": node.lineno, "end_line": node.end_lineno}
                        for node in ast.walk(tree)
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                except (SyntaxError, UnicodeError) as exc:
                    entry["parse_error"] = str(exc)
        inventory.append(entry)
    write_json("inventory.json", inventory)

    plan_data = args.plan.resolve().read_bytes()
    text = plan_data.decode("utf-8-sig")
    week = None
    section = None
    checklist = []
    counts: Counter[str] = Counter()
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"# Tuần (\d+)–(\d+) —", line)
        if match:
            week = f"W{int(match[1]):02d}-{int(match[2]):02d}"
        if line.startswith("## "):
            section = line[3:]
        item = re.match(r"(\s*)- \[([ xX])\] (.+)", line)
        if item:
            if week is None or section is None:
                raise ValueError(f"Unassigned checklist at plan line {line_number}")
            owner = (section.split(" — ")[0] if section.startswith(("M1 —", "M2 —", "M3 —"))
                     else ("DOD" if section == "Definition of Done" else "CHUNG"))
            group = f"{week}-{owner}"
            counts[group] += 1
            checklist.append({"id": f"{group}-{counts[group]:02d}", "week": week,
                              "owner": owner, "section": section, "line": line_number,
                              "text": item[3], "nested": bool(item[1]),
                              "original_checked": item[2].lower() == "x"})
    write_json("plan-checklist.json", checklist)

    packages = {}
    for name in ("pytest", "pydantic", "mcp", "langchain", "langgraph",
                 "langchain-mcp-adapters", "tree-sitter", "tree-sitter-python",
                 "torch", "transformers", "tokenizers", "pyarrow", "datasets",
                 "peft", "trl", "matplotlib"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "MISSING"
    tests = {}
    for name in ("main-baseline", "integrated-tests"):
        xml_path = OUTPUT / f"{name}.xml"
        if not xml_path.exists():
            continue
        suite = ET.parse(xml_path).getroot().find("testsuite")
        tests[name] = {"suite": dict(suite.attrib),
                       "non_passing": [{"class": case.get("classname"), "name": case.get("name"),
                                        "outcome": child.tag, "message": child.get("message")}
                                       for case in suite.findall("testcase") for child in case
                                       if child.tag in {"failure", "error", "skipped"}]}
    snapshot = {"audit_date_local": "2026-10-13", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "repo": str(ROOT), "branch": git("branch", "--show-current"),
                "head": git("rev-parse", "HEAD"), "main_sha": git("rev-parse", "origin/main"),
                "m1_sha": git("rev-parse", "origin/m1-w5-w6-20261010"),
                "main_is_ancestor": subprocess.run(["git", "merge-base", "--is-ancestor",
                                                       "origin/main", "HEAD"], cwd=ROOT).returncode == 0,
                "plan": str(args.plan.resolve()), "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
                "tracked_files": len(tracked), "directories": dict(Counter(p.split('/')[0] for p in tracked)),
                "checklist_items": len(checklist), "checklist_by_group": dict(counts),
                "python": sys.version, "interpreter": sys.executable, "platform": platform.platform(),
                "packages": packages, "tests": tests}
    write_json("snapshot.json", snapshot)
    report = ROOT / "Task Status.md"
    if report.exists():
        report_text = report.read_text(encoding="utf-8")
        matches = re.findall(
            r"(?m)^\| (W\d{2}-\d{2}-(?:CHUNG|M[123]|DOD)-\d{2}) \|[^\n]*?\| \*\*(HT|MP|CT|CX)\*\* \|",
            report_text,
        )
        actual = [item[0] for item in matches]
        expected = {item["id"] for item in checklist}
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        duplicates = sorted(key for key, count in Counter(actual).items() if count != 1)
        missing_links = []
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", report_text):
            if target.startswith(("https://", "http://", "#")):
                continue
            link_path = target.split("#", 1)[0]
            if not (ROOT / link_path).exists():
                missing_links.append(target)
        status_by_week = {}
        for identifier, status in matches:
            group = identifier[:6]
            status_by_week.setdefault(group, Counter())[status] += 1
        qa = {"canonical_checklist_count": len(checklist), "report_rows": len(matches),
              "missing_ids": missing, "extra_ids": extra, "duplicate_ids": duplicates,
              "broken_local_links": sorted(set(missing_links)),
              "status_counts": dict(Counter(status for _, status in matches)),
              "status_by_week": {group: dict(counts) for group, counts in status_by_week.items()},
              "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
              "product_worktree_matches_head": subprocess.run(
                  ["git", "diff", "--quiet", "HEAD", "--", "src", "tests", "scripts",
                   "configs", "artifacts", "README.md", "pyproject.toml", ".env.example", ".gitignore"],
                  cwd=ROOT,
              ).returncode == 0}
        write_json("report-qa.json", qa)
        if missing or extra or duplicates or missing_links:
            raise ValueError(f"Report QA failed: {qa}")
    print(json.dumps({"tracked_files": len(tracked), "checklist_items": len(checklist),
                      "python_parse_errors": sum("parse_error" in x for x in inventory),
                      "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
