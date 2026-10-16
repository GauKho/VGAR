"""Read-only documentation/source QA; writes only a new validation report."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[3]
AUDIT = Path(__file__).resolve().parent
EXPECTED_UNCHANGED = {
    "src/vgar/evaluation/retrieval/compare.py": "1e88a8a97b0845eb5579322841991debaee00b9c779cf5e462737965a8f013b6",
    "src/vgar/evaluation/retrieval/scoring.py": "dfbad5552d67a42dffac9f22f54ef58f8b397f8c88825fab719e4772b97293b8",
    "Task Status.md": "cab8b4a214b1abe117044cf741b4da91523d811e4a486c83a2c778b5379d7dcb",
    "pyproject.toml": "d521f0424030c7e577b6be0d52257a743570cafb2fac39115b5be833cf8d23e3",
    "M2_week_7_8/requirement.txt": "c81b5c19aa7d14fe101a7cfeb4ac022e431334994439a80192100986e901edb2",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_counts(path: Path) -> dict:
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    result = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    result["passed"] = result["tests"] - result["failures"] - result["errors"] - result["skipped"]
    return result


def main() -> None:
    started = datetime.now(timezone.utc)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\ufffd" not in readme and chr(167) not in readme
    lines = readme.splitlines()
    prose = []
    tables = []
    fenced = False
    table_columns = None
    for number, line in enumerate(lines, 1):
        if line.startswith("§§§".replace("§", chr(96))):
            fenced = not fenced
            table_columns = None
            continue
        if fenced:
            continue
        prose.append(line)
        if line.startswith("|"):
            assert line.endswith("|"), (number, "table end")
            count = len(re.split(r"(?<!\\)\|", line)) - 2
            if table_columns is None:
                table_columns = count
                tables.append({"line": number, "columns": count})
                assert number > 1 and not lines[number - 2].strip(), (number, "table requires blank line")
            assert count == table_columns, (number, count, table_columns)
        else:
            table_columns = None
    assert not fenced, "Unclosed code fence"
    prose_text = "\n".join(prose)
    headings = re.findall(r"^#{1,6}\s+(.+)$", prose_text, flags=re.M)
    slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
    checked_links = []
    for target in re.findall(r"(?<!!)\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)\)", prose_text):
        target = unquote(target.strip("<>"))
        if re.match(r"https?://", target):
            continue  # No network requests/claims about external link availability.
        path, _, anchor = target.partition("#")
        if not path:
            assert anchor in slugs, ("missing heading", anchor)
        else:
            assert (ROOT / path).exists(), ("missing local link", target)
        checked_links.append(target)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    entries = [str(Requirement(line.strip())) for line in
               (ROOT / "requirement.txt").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    expected = [str(Requirement(item)) for item in
                project["dependencies"] + project["optional-dependencies"]["dev"]
                + project["optional-dependencies"]["plot"]]
    assert Counter(entries) == Counter(expected), ("requirements/metadata mismatch", entries, expected)
    assert len(entries) == len(set(entries)), "Duplicate requirements"
    preserved = {}
    for name, expected_sha in EXPECTED_UNCHANGED.items():
        observed = sha(ROOT / name)
        assert observed == expected_sha, ("out-of-scope drift", name, observed)
        preserved[name] = observed
    status_qa = json.loads((ROOT / "docs/audit/2026-10-16-task-status-update/task-status-qa.json").read_text())
    assert status_qa["counts"] == {"HT": 47, "MP": 48, "CT": 25, "CX": 30}
    assert sha(ROOT / "Task Status.md") == status_qa["task_status_sha256"]
    for fragment in ("47 HT / 48 MP / 25 CT / 30 CX", "571 PASS, 1 FAIL, 2 SKIP", "236"):
        assert fragment in readme, ("missing status", fragment)
    core = ROOT / "M2_week_7_8/results/integration-qualification/final-core-suite/20261016T070502676971Z-3cde4ebc98db"
    core_counts = xml_counts(core / "junit.xml")
    root_counts = xml_counts(ROOT / "docs/audit/2026-10-16-m2-w7-w8-integration/final-vgar-suite.xml")
    assert core_counts == dict(tests=236, failures=0, errors=0, skipped=0, passed=236)
    assert root_counts == dict(tests=574, failures=1, errors=0, skipped=2, passed=571)
    manifest = json.loads((ROOT / "M2_week_7_8/results/final_acceptance/2026-10-15-v11-r002/run_manifest.json").read_text())
    assert manifest["status"] == "PASS" and manifest["complete"]
    assert set(manifest["cases"]) == set("ABC")
    assert all(c["status"] == "PASS" for c in manifest["cases"].values())
    assert manifest["input_tokens_sum"] == 4237 and manifest["output_tokens_sum"] == 243
    assert manifest["runtime_revision"] == "r002" and manifest["prompt_version"] == "m2-w78-v11"
    profile = json.loads((ROOT / "M2_week_7_8/config/demo.json").read_text())
    assert profile["model"]["revision"] == "cdbee75f17c01a7cc42f958dc650907174af0554"
    assert profile["policy"]["input_cap"] == 6000 and profile["policy"]["output_cap"] == 1536
    assert sha(ROOT / "M2_week_7_8/prompts/repair_v11.txt") == "ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8"
    path = str(ROOT / "README.md").replace("'", "''")
    powershell = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$content = Get-Content -Raw -Encoding UTF8 -LiteralPath '__PATH__'
$blocks = [regex]::Matches($content, '(?ms)^§§§powershell\r?\n(.*?)^§§§\s*$')
$errorsFound = @()
for ($i = 0; $i -lt $blocks.Count; $i++) {
    $tokens = $null; $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($blocks[$i].Groups[1].Value, [ref]$tokens, [ref]$parseErrors)
    foreach ($e in $parseErrors) {
        $errorsFound += [pscustomobject]@{block=$i+1;message=$e.Message;line=$e.Extent.StartLineNumber}
    }
}
[pscustomobject]@{blocks=$blocks.Count;errors=@($errorsFound)} | ConvertTo-Json -Depth 6 -Compress
""".replace("§", chr(96)).replace("__PATH__", path)
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", powershell],
                            capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    syntax = json.loads(result.stdout)
    assert syntax["blocks"] > 0 and syntax["errors"] == [], syntax
    # This checks syntax ONLY: none of the README command blocks is executed.
    report = {
        "status": "PASS", "scope": "documentation/static QA; no installs/test/model runs",
        "started_utc": started.isoformat(), "ended_utc": datetime.now(timezone.utc).isoformat(),
        "readme_lines": len(lines), "markdown_tables": tables,
        "checked_local_links_and_anchors": len(checked_links), "powershell_ast": syntax,
        "requirements_match_pyproject_runtime_and_dev_plot": True, "requirement_entries": len(entries),
        "clean_dependency_resolution_verified": False, "historical_core_counts": core_counts,
        "historical_root_counts": root_counts, "historical_real_manifest": manifest["status"],
        "preserved": preserved, "sha256": {
            name: sha(ROOT / name) for name in ("README.md", "requirement.txt", "PROGRESS.md")},
        "readme_before_sha256": sha(AUDIT / "README.before.md"),
    }
    output = AUDIT / ("validation-" + started.strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "readme_lines": len(lines),
                     "tables": len(tables), "links_and_anchors": len(checked_links),
                     "requirements": len(entries), "powershell_blocks": syntax["blocks"],
                     "report": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
