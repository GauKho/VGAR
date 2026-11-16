"""Run RefactoringMiner 3.2.0 and GumTree 4.1.0 (proposal §7.3 steps 1 and 3) on the benchmark; record outputs + wall time.

Usage:  python run_java_tools.py            (smoke test, then everything; re-running skips finished items)
Outputs: out/rm/*.json, out/gt/*.json, out/timings.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Work folder (benchmark git repo, tool downloads, outputs): outside this repository on purpose.
WORK = Path(os.environ.get("VGAR_GRAPHDIFF_WORK", Path(tempfile.gettempdir()) / "vgar-graphdiff-bench"))
TOOLS = WORK / "tools"  # tools/rm/RefactoringMiner-3.2.0, tools/gt/gumtree-4.1.0 (unzipped releases)
JAVA_HOME = Path(os.environ.get("VGAR_JAVA_HOME", r"D:\tools\jdk21\jdk-21.0.13+9"))
RM = next((TOOLS / "rm").glob("*/bin/RefactoringMiner.bat"))
GT = next((TOOLS / "gt").glob("*/bin/gumtree.bat"))
# RefactoringMiner.bat lists 100+ jars in one CLASSPATH line, longer than cmd.exe accepts: call java directly
RM_JAVA = [str(JAVA_HOME / "bin" / "java.exe"), "-classpath", str(RM.parent.parent / "lib" / "*"),
           "org.refactoringminer.RefactoringMiner"]
OUT = WORK / "out"
ENV = {**os.environ, "JAVA_HOME": str(JAVA_HOME), "PATH": f"{JAVA_HOME / 'bin'};{os.environ['PATH']}"}
GOLD = json.loads((WORK / "bench" / "gold.json").read_text(encoding="utf-8"))
TIMINGS_FILE = OUT / "timings.json"
timings = json.loads(TIMINGS_FILE.read_text(encoding="utf-8")) if TIMINGS_FILE.exists() else {}


def save() -> None:
    TIMINGS_FILE.write_text(json.dumps(timings, indent=1), encoding="utf-8")


def run(cmd: list[str], timeout: int) -> tuple[float, subprocess.CompletedProcess | None]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(cmd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return time.perf_counter() - start, None
    return time.perf_counter() - start, proc


def git(repo: str, *args: str) -> bytes:
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True).stdout


def refactoringminer(key: str, repo: str, sha: str, timeout: int) -> bool:
    target = OUT / "rm" / f"{key}.json"
    if key in timings.get("rm", {}) and target.exists():
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    seconds, proc = run([*RM_JAVA, "-c", repo, sha, "-json", str(target)], timeout)
    ok = proc is not None and proc.returncode == 0 and target.exists()
    timings.setdefault("rm", {})[key] = {"seconds": round(seconds, 3), "ok": ok,
                                         "error": None if ok else (proc.stderr[-2000:] if proc else "timeout")}
    save()
    return ok


def gumtree(key: str, before: bytes, after: bytes, timeout: int = 300) -> bool:
    target = OUT / "gt" / f"{key}.json"
    if key in timings.get("gt", {}) and target.exists():
        return True
    files = OUT / "files"
    files.mkdir(parents=True, exist_ok=True)
    a, b = files / f"{key}.before.py", files / f"{key}.after.py"
    a.write_bytes(before)
    b.write_bytes(after)
    target.parent.mkdir(parents=True, exist_ok=True)
    seconds, proc = run(["cmd", "/c", str(GT), "textdiff", "-g", "python-treesitter-ng", "-f", "JSON", str(a), str(b)],
                        timeout)
    ok = proc is not None and proc.returncode == 0 and proc.stdout.lstrip().startswith("{")
    if ok:
        target.write_text(proc.stdout, encoding="utf-8")
    timings.setdefault("gt", {})[key] = {"seconds": round(seconds, 3), "ok": ok,
                                         "error": None if ok else (proc.stderr[-2000:] if proc else "timeout")}
    save()
    return ok


def file_pairs(repo: str, parent: str, sha: str, paths: list[str] | None = None) -> list[tuple[str, bytes, bytes]]:
    if paths is None:
        lines = git(repo, "diff-tree", "--no-commit-id", "-r", "--name-status", parent, sha).decode().splitlines()
        paths = [line.split("\t")[1] for line in lines if line.startswith("M\t") and line.endswith(".py")]
    return [(p, git(repo, "show", f"{parent}:{p}"), git(repo, "show", f"{sha}:{p}")) for p in paths]


def main() -> int:
    bench, vgar = GOLD["bench_repo"], GOLD["vgar_repo"]
    first = GOLD["scenarios"][0]
    print("smoke test ...", flush=True)
    rm_ok = refactoringminer(f"bench-{first['sha'][:12]}", bench, first["sha"], 600)
    _path, before, after = file_pairs(bench, first["parent"], first["sha"])[0]
    gt_ok = gumtree(f"bench-{first['sha'][:12]}-0", before, after)
    if not (rm_ok and gt_ok):
        print("SMOKE FAILED; send this file to Claude:", TIMINGS_FILE)
        print(json.dumps({k: v for k, v in timings.items()}, indent=1)[-4000:])
        return 2
    # JVM start-up baseline: GumTree on two identical one-line files, five times
    for i in range(5):
        gumtree(f"baseline-{i}", b"x = 1\n", b"x = 1\n")
    for n, s in enumerate(GOLD["scenarios"], 1):
        print(f"[bench {n}/{len(GOLD['scenarios'])}] {s['bug']} {s['variant']}", flush=True)
        refactoringminer(f"bench-{s['sha'][:12]}", bench, s["sha"], 600)
        for i, (_p, before, after) in enumerate(file_pairs(bench, s["parent"], s["sha"])):
            gumtree(f"bench-{s['sha'][:12]}-{i}", before, after)
    # one JVM for the whole benchmark range (amortised start-up); scenarios are every second commit
    if "rm_bc" not in timings:
        target = OUT / "rm" / "bench-range.json"
        seconds, proc = run([*RM_JAVA, "-bc", bench, GOLD["scenarios"][0]["parent"],
                             GOLD["scenarios"][-1]["sha"], "-json", str(target)], 3600)
        timings["rm_bc"] = {"seconds": round(seconds, 3), "ok": proc is not None and proc.returncode == 0,
                            "commits": 2 * len(GOLD["scenarios"]) - 1}
        save()
    for n, h in enumerate(GOLD["history"], 1):
        print(f"[history {n}/{len(GOLD['history'])}] {h['sha'][:12]} ({len(h['modified_py'])} files)", flush=True)
        refactoringminer(f"hist-{h['sha'][:12]}", vgar, h["sha"], 900)
        for i, (_p, before, after) in enumerate(file_pairs(vgar, f"{h['sha']}^", h["sha"], h["modified_py"])):
            gumtree(f"hist-{h['sha'][:12]}-{i}", before, after)
    bad = [(tool, k) for tool in ("rm", "gt") for k, v in timings.get(tool, {}).items() if not v["ok"]]
    print("done;", len(bad), "failures", bad[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
