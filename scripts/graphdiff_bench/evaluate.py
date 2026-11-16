"""Compare GraphDiff pipelines on the labelled benchmark and on real history.

  A  ast      : TV3 read_commit_history + diff_python_commit; refactorings = exact-body ADDED/REMOVED pairs
  P  proposal : GumTree 4.1.0 edit actions (step 3) + RefactoringMiner 3.2.0 refactorings (step 1)
  H  hybrid   : ast symbol edits + RefactoringMiner refactorings
Every pipeline goes through the same steps 4-5 here: map edits to symbols ("path::Qual.name" / "path::<module>"),
drop symbols that a detected refactoring involves, and drop symbols whose change is only the renamed references.
The remaining symbols are the predicted bug-fix edits, scored against the known labels.
"""
from __future__ import annotations

import ast
import json
import os
import re
import statistics
import sys
import tempfile
import textwrap
import time
from collections import Counter, defaultdict
from pathlib import Path

# Work folder (benchmark git repo, tool downloads, outputs): outside this repository on purpose.
WORK = Path(os.environ.get("VGAR_GRAPHDIFF_WORK", Path(tempfile.gettempdir()) / "vgar-graphdiff-bench"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vgar.graph.ast_diff import diff_python_commit
from vgar.graph.history import read_commit_history

GOLD = json.loads((WORK / "bench" / "gold.json").read_text(encoding="utf-8"))
OUT = WORK / "out"
TIMINGS = json.loads((OUT / "timings.json").read_text(encoding="utf-8")) if (OUT / "timings.json").exists() else {}
DEFS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


# ------------------------------------------------------------------ helpers
def definitions(text: str) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}

    def walk(body, scope):
        for node in body:
            if isinstance(node, DEFS):
                out.setdefault(scope + node.name, node)
                if isinstance(node, ast.ClassDef):
                    walk(node.body, scope + node.name + ".")
    walk(ast.parse(text).body, "")
    return out


def span(node) -> tuple[int, int]:
    return min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno


def enclosing(defs: dict[str, ast.AST], line: int) -> str:
    best, size = "<module>", 10 ** 9
    for name, node in defs.items():
        start, end = span(node)
        if start <= line <= end and end - start < size:
            best, size = name, end - start
    return best


def shape(node) -> str:
    """Definition without its own name or positions (for exact-body pairing)."""
    clone = ast.parse(ast.unparse(node)).body[0]
    clone.name = "_"
    return ast.dump(clone)


def module_statements(text: str, drop_names: set[str]) -> list[str]:
    out = []
    for node in ast.parse(text).body:
        if isinstance(node, DEFS):
            continue
        if isinstance(node, ast.ImportFrom):
            node.names = [a for a in node.names if a.name not in drop_names]
            if not node.names:
                continue
        out.append(ast.dump(node))
    return out


def rename_tokens(source: str, mapping: dict[str, str]) -> str:
    for new, old in mapping.items():
        source = re.sub(rf"\b{re.escape(new)}\b", old, source)
    return source


def segment(text: str, node) -> str:
    start, end = span(node)
    return textwrap.dedent("\n".join(text.splitlines()[start - 1:end]))


class Commit:
    """Before/after text of every modified .py file of one commit, read through dulwich (L4-1 objects)."""

    def __init__(self, repo: str, sha: str):
        from dulwich.repo import Repo
        self.change, = read_commit_history(repo, revision=sha, max_commits=1).commits
        self.files: dict[str, tuple[str | None, str | None]] = {}
        with Repo(repo) as r:
            for fc in self.change.files:
                path = (fc.after or fc.before).path
                if not path.endswith(".py"):
                    continue
                read = lambda v: r.get_object(v.object_id.encode()).data.decode("utf-8") if v else None
                self.files[path] = (read(fc.before), read(fc.after))
        self.defs = {p: (definitions(a) if a else {}, definitions(b) if b else {}) for p, (a, b) in self.files.items()}


# ------------------------------------------------------------------ step 3: edits per pipeline
def ast_edits(repo: str, commit: Commit) -> tuple[set[str], set[str]]:
    """(changed symbols, symbols on the MODIFIED list) from TV3's diff_python_commit."""
    changed, modified = set(), set()
    for fd in diff_python_commit(repo, commit.change):
        path = (fd.after or fd.before).path
        for e in fd.ast_diff.edits:
            changed.add(f"{path}::{e.symbol}")
            if e.change == "MODIFIED":
                modified.add(f"{path}::{e.symbol}")
        if fd.ast_diff.module_statements_changed:
            changed.add(f"{path}::<module>")
            modified.add(f"{path}::<module>")
    return changed, modified


POS = re.compile(r"\[(\d+),(\d+)\]\s*$")


def gumtree_edits(key_prefix: str, commit: Commit, paths: list[str]) -> set[str] | None:
    changed = set()
    for i, path in enumerate(paths):
        f = OUT / "gt" / f"{key_prefix}-{i}.json"
        if not f.exists():
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
        before, after = commit.files[path]
        dbefore, dafter = commit.defs[path]
        sides = {"src": before, "dst": after}
        line_of = lambda raw, off: raw[:off].count("\n") + 1
        for act in data.get("actions", []):
            kind = act["action"]
            refs = []
            if kind.startswith("insert"):
                refs.append(("dst", act["tree"]))
            else:
                refs.append(("src", act["tree"]))
            if kind == "move-tree" and "parent" in act:
                refs.append(("dst", act["parent"]))
            for side, tree in refs:
                m = POS.search(tree)
                if not m:
                    continue
                start = int(m[1])
                defs = dbefore if side == "src" else dafter
                # an action on a whole definition belongs to that definition, otherwise to the innermost one
                name = enclosing(defs, line_of(sides[side], start))
                changed.add(f"{path}::{name}")
    return changed


# ------------------------------------------------------------------ step 1: refactorings per pipeline
FAMILIES = [("rename method", "rename_method"), ("rename function", "rename_method"),
            ("rename class", "rename_class"), ("move class", "move_class"), ("extract and move", "extract_method"),
            ("extract method", "extract_method"), ("extract function", "extract_method"),
            ("move and rename", "move_method"), ("move method", "move_method"), ("move function", "move_method"),
            ("move operation", "move_method"), ("rename parameter", "rename_parameter"),
            ("rename variable", "rename_variable"), ("rename local variable", "rename_variable"),
            ("inline method", "inline_method"), ("inline function", "inline_method")]


def family_of(rtype: str) -> str:
    low = rtype.lower()
    return next((fam for key, fam in FAMILIES if low.startswith(key)), "other:" + rtype)


def ast_refactorings(commit: Commit, changed: set[str]) -> list[dict]:
    removed, added = [], []
    for path, (dbefore, dafter) in commit.defs.items():
        for name in dbefore.keys() - dafter.keys():
            removed.append((path, name, dbefore[name]))
        for name in dafter.keys() - dbefore.keys():
            added.append((path, name, dafter[name]))
    pairs, used = [], set()
    for rp, rn, rnode in removed:
        for ap, an, anode in added:
            if (ap, an) in used or type(rnode) is not type(anode) or shape(rnode) != shape(anode):
                continue
            if rp == ap and rn == an:
                continue
            used.add((ap, an))
            pairs.append((rp, rn, ap, an, rnode))
            break
    out = []
    paired_classes = {(rp, rn) for rp, rn, ap, an, node in pairs if isinstance(node, ast.ClassDef)}
    for rp, rn, ap, an, node in pairs:
        parent = rn.rsplit(".", 1)[0] if "." in rn else None
        if parent and (rp, parent) in paired_classes:
            continue  # member of a renamed/moved class
        short_old, short_new = rn.split(".")[-1], an.split(".")[-1]
        if isinstance(node, ast.ClassDef):
            fam = "rename_class" if rp == ap else "move_class"
        else:
            fam = "rename_method" if rp == ap else "move_method"
        involved = {f"{rp}::{rn}", f"{ap}::{an}"}
        if isinstance(node, ast.ClassDef):
            involved |= {f"{rp}::{n}" for n in commit.defs[rp][0] if n.startswith(rn + ".")}
            involved |= {f"{ap}::{n}" for n in commit.defs[ap][1] if n.startswith(an + ".")}
        out.append({"family": fam, "description": f"{fam} {rp}::{rn} -> {ap}::{an}", "involved": involved,
                    "rename": {short_new: short_old} if short_old != short_new else {},
                    "names": {short_old, short_new}})
    return out


def rm_refactorings(key: str, commit: Commit) -> list[dict] | None:
    f = OUT / "rm" / f"{key}.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text(encoding="utf-8"))
    out = []
    for c in data.get("commits", []):
        for r in c.get("refactorings", []):
            involved, names = set(), set()
            for side, locs in ((0, r.get("leftSideLocations", [])), (1, r.get("rightSideLocations", []))):
                for loc in locs:
                    path = loc["filePath"].replace("\\", "/")
                    if path not in commit.defs:
                        continue
                    defs = commit.defs[path][side]
                    name = next((n for n, node in defs.items() if span(node)[0] <= loc["startLine"] <= node.lineno),
                                None) or enclosing(defs, loc["startLine"])
                    involved.add(f"{path}::{name}")
                    if "DECLARATION" in loc.get("codeElementType", "") and name != "<module>":
                        names.add(name.split(".")[-1])
            fam = family_of(r["type"])
            if fam == "rename_class" or r["type"].lower().startswith("move class"):
                # same rule as the ast detector: members of a renamed/moved class move with it
                for sym in list(involved):
                    path, name = sym.split("::", 1)
                    for defs in commit.defs[path]:
                        if isinstance(defs.get(name), ast.ClassDef):
                            involved |= {f"{path}::{n}" for n in defs if n.startswith(name + ".")}
            rename = {}
            if fam in ("rename_method", "rename_class", "move_method") and len(names) == 2:
                desc = r.get("description", "")
                old = min(names, key=lambda n: desc.find(n) if n in desc else 10 ** 9)  # RM names the old one first
                rename = {(names - {old}).pop(): old}
            out.append({"family": fam, "description": r.get("description", r["type"]), "involved": involved,
                        "rename": rename, "names": names})
    return out


# ------------------------------------------------------------------ steps 4-5: filter
def predicted_bugfix(commit: Commit, changed: set[str], refactorings: list[dict]) -> set[str]:
    involved = set().union(*(r["involved"] for r in refactorings)) if refactorings else set()
    mapping: dict[str, str] = {}
    names: set[str] = set()
    for r in refactorings:
        mapping.update(r["rename"])
        names |= r["names"]
    keep = set()
    for sym in changed - involved:
        path, name = sym.split("::", 1)
        before, after = commit.files.get(path, (None, None))
        if before is None or after is None:
            keep.add(sym)
            continue
        if name == "<module>":
            if module_statements(rename_tokens(after, mapping), names) == module_statements(before, names):
                continue
            keep.add(sym)
            continue
        dbefore, dafter = commit.defs[path]
        if name in dbefore and name in dafter and mapping:
            try:
                same = ast.dump(ast.parse(rename_tokens(segment(after, dafter[name]), mapping))) == \
                    ast.dump(ast.parse(segment(before, dbefore[name])))
            except SyntaxError:
                same = False
            if same:
                continue
        keep.add(sym)
    return keep


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main() -> None:
    bench = GOLD["bench_repo"]
    rows = []
    for s in GOLD["scenarios"]:
        t0 = time.perf_counter()
        commit = Commit(bench, s["sha"])
        changed, _modified = ast_edits(bench, commit)
        a_ref = ast_refactorings(commit, changed)
        a_pred = predicted_bugfix(commit, changed, a_ref)
        ast_seconds = time.perf_counter() - t0
        key = f"bench-{s['sha'][:12]}"
        paths = [p for p, (b, a) in commit.files.items() if b is not None and a is not None and b != a]
        rm = rm_refactorings(key, commit)
        gt = gumtree_edits(key, commit, sorted(paths))
        rows.append({"s": s, "ast_seconds": ast_seconds, "ast_changed": changed, "ast_ref": a_ref,
                     "A": a_pred, "rm": rm, "gt": gt,
                     "P": predicted_bugfix(commit, gt, rm) if rm is not None and gt is not None else None,
                     "H": predicted_bugfix(commit, changed, rm) if rm is not None else None})
    report(rows)
    history_report()


def history_report() -> None:
    """Real history of this repository: speed, and agreement between the two refactoring detectors (no labels)."""
    vgar = GOLD["vgar_repo"]
    lines = ["", "## Real history (30 first-parent commits of vgar_mcp_mvp_demo, no labels)", "",
             "| Commit | py files | ast ms | ast refactorings | RM s | RM refactorings (rename/move) | GumTree s |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    totals = Counter()
    agree = Counter()
    for h in GOLD["history"]:
        t0 = time.perf_counter()
        try:
            commit = Commit(vgar, h["sha"])
            changed, _ = ast_edits(vgar, commit)
            a_ref = ast_refactorings(commit, changed)
        except Exception as exc:  # noqa: BLE001 - report the failure instead of hiding the commit
            lines.append(f"| {h['sha'][:10]} | {len(h['modified_py'])} | ast failed: {type(exc).__name__} | | | | |")
            continue
        ms = (time.perf_counter() - t0) * 1000
        key = f"hist-{h['sha'][:12]}"
        rm_t = TIMINGS.get("rm", {}).get(key)
        rm = rm_refactorings(key, commit) if rm_t and rm_t["ok"] else None
        gt_s = sum(v["seconds"] for k, v in TIMINGS.get("gt", {}).items() if k.startswith(key + "-"))
        a_rm = {frozenset(x["names"]) for x in a_ref}
        r_rm = {frozenset(x["names"]) for x in (rm or []) if x["family"] in ("rename_method", "rename_class",
                                                                             "move_method", "move_class")}
        agree["ast"] += len(a_rm)
        agree["rm"] += len(r_rm)
        agree["both"] += len(a_rm & r_rm)
        totals["ast_ms"] += ms
        totals["rm_s"] += rm_t["seconds"] if rm_t else 0
        totals["gt_s"] += gt_s
        rm_cell = "n/a" if rm is None else f"{len(rm)} ({len(r_rm)})"
        lines.append(f"| {h['sha'][:10]} | {len(h['modified_py'])} | {ms:.0f} | {len(a_ref)} | "
                     f"{rm_t['seconds'] if rm_t else 'n/a'} | {rm_cell} | {gt_s:.1f} |")
    lines.append(f"| **total** | {sum(len(h['modified_py']) for h in GOLD['history'])} | {totals['ast_ms']:.0f} | "
                 f"{agree['ast']} | {totals['rm_s']:.1f} | ({agree['rm']}) | {totals['gt_s']:.1f} |")
    lines.append("")
    lines.append(f"Rename/move pairs found by ast: {agree['ast']}, by RefactoringMiner: {agree['rm']}, "
                 f"by both (same name pair): {agree['both']}")
    with open(WORK / "report.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def report(rows) -> None:
    lines = ["# GraphDiff benchmark: ast vs proposal tools", ""]
    have_java = all(r["rm"] is not None and r["gt"] is not None for r in rows)
    lines.append(f"Scenarios: {len(rows)} (17 bugs x pure / format / refactor / refactor+format). "
                 f"Java tool outputs present: {have_java}")
    # bug-fix isolation
    lines += ["", "## Bug-fix edit isolation (symbol level)", "",
              "| Pipeline | Variant | P | R | F1 | FP from refactor | FP from format | other FP |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for pipe in ("A", "P", "H"):
        if any(r[pipe] is None for r in rows):
            continue
        for variant in ("pure", "format", "refactor", "refactor+format", "ALL"):
            sel = [r for r in rows if variant == "ALL" or r["s"]["variant"] == variant]
            tp = fp = fn = fr = ff = 0
            for r in sel:
                gold = set(r["s"]["gold_bugfix"])
                pred = r[pipe]
                tp += len(pred & gold)
                fn += len(gold - pred)
                extra = pred - gold
                fp += len(extra)
                fr += len(extra & set(r["s"]["gold_refactor"]))
                ff += len(extra & set(r["s"]["gold_format"]))
            p, rc, f1 = prf(tp, fp, fn)
            name = {"A": "ast (TV3)", "P": "GumTree + RefactoringMiner", "H": "ast + RefactoringMiner"}[pipe]
            lines.append(f"| {name} | {variant} | {p:.2f} | {rc:.2f} | {f1:.2f} | {fr} | {ff} | {fp - fr - ff} |")
    # refactoring detection
    lines += ["", "## Refactoring detection (step 1)", "", "| Detector | Family | gold | found | reported (all) |",
              "|---|---|---:|---:|---:|"]
    for det, field in (("ast exact-body pairs", "ast_ref"), ("RefactoringMiner 3.2.0", "rm")):
        if any(r[field] is None for r in rows):
            continue
        per = defaultdict(lambda: [0, 0])
        reported = Counter()
        tp_all = rep_all = 0
        for r in rows:
            gold = r["s"]["refactoring"]
            rep_all += len(r[field])
            for x in r[field]:
                reported[x["family"]] += 1
            if gold:
                per[gold["family"]][0] += 1
                hit = any(x["family"] == gold["family"] and any(e in x["description"] for e in gold["entities"])
                          for x in r[field])
                per[gold["family"]][1] += hit
                tp_all += hit
        for fam, (g, f) in sorted(per.items()):
            lines.append(f"| {det} | {fam} | {g} | {f} | {reported.get(fam, 0)} |")
        gold_total = sum(g for g, _ in per.values())
        extra = {k: v for k, v in reported.items() if k not in per}
        lines.append(f"| {det} | **total** | {gold_total} | {tp_all} (recall {tp_all / gold_total:.2f}) | "
                     f"{rep_all} (precision {tp_all / rep_all if rep_all else 0:.2f}) |")
        if extra:
            lines.append(f"| {det} | not in gold | | | {dict(extra)} |")
    # speed
    lines += ["", "## Speed (benchmark commits)", ""]
    ast_t = [r["ast_seconds"] for r in rows]
    lines.append(f"- ast (TV3, in-process): median {statistics.median(ast_t) * 1000:.0f} ms/commit, "
                 f"max {max(ast_t) * 1000:.0f} ms")
    if TIMINGS:
        base = [v["seconds"] for k, v in TIMINGS.get("gt", {}).items() if k.startswith("baseline")]
        rm_b = [v["seconds"] for k, v in TIMINGS.get("rm", {}).items() if k.startswith("bench") and v["ok"]]
        gt_b = defaultdict(float)
        for k, v in TIMINGS.get("gt", {}).items():
            if k.startswith("bench") and v["ok"]:
                gt_b[k.rsplit("-", 1)[0]] += v["seconds"]
        if rm_b:
            lines.append(f"- RefactoringMiner (one JVM per commit): median {statistics.median(rm_b):.2f} s/commit")
        if "rm_bc" in TIMINGS and TIMINGS["rm_bc"]["ok"]:
            bc = TIMINGS["rm_bc"]
            lines.append(f"- RefactoringMiner (one JVM, -bc over {bc['commits']} commits): "
                         f"{bc['seconds'] / bc['commits']:.2f} s/commit amortised")
        if base:
            lines.append(f"- GumTree JVM start-up (identical 1-line files): median {statistics.median(base):.2f} s")
        if gt_b:
            per_file = [v["seconds"] for k, v in TIMINGS["gt"].items() if k.startswith("bench") and v["ok"]]
            lines.append(f"- GumTree: median {statistics.median(per_file):.2f} s/file, "
                         f"{statistics.median(gt_b.values()):.2f} s/commit (one JVM per file)")
            if base:
                lines.append(f"  - minus start-up: ~{max(0.0, statistics.median(per_file) - statistics.median(base)):.2f}"
                             " s/file of diff work")
    (WORK / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    # per-scenario detail for inspection
    detail = [{"bug": r["s"]["bug"], "variant": r["s"]["variant"], "gold": r["s"]["gold_bugfix"],
               "A": sorted(r["A"]), "P": sorted(r["P"]) if r["P"] is not None else None,
               "H": sorted(r["H"]) if r["H"] is not None else None,
               "ast_ref": [x["description"] for x in r["ast_ref"]],
               "rm": [x["description"] for x in r["rm"]] if r["rm"] is not None else None} for r in rows]
    (WORK / "detail.json").write_text(json.dumps(detail, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
