"""Spike: score static/SCIP/MAY_CALL/PyCG against the `# expect:` annotations, per group. Args: <cases dir> [pycg|jarvis]. The "pycg" columns hold the chosen tool."""
import collections
import json
import os
import re
import sys
from pathlib import Path

CASES = Path(sys.argv[1])
TOOL = sys.argv[2] if len(sys.argv) > 2 else "pycg"
EXPECT = re.compile(r"#\s*expect:\s*([^#]+)")
MODES = ["static", "static+MAY", "scip", "scip+MAY", "pycg", "scip>pycg", "scip>pycg>MAY"]


def norm(name):
    return re.sub(r"<lambda\d*>", "<lambda>", name.replace(".<locals>", "").replace("\\", "."))


def expectations(repo, source_root):
    out = {}
    for path in sorted(source_root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = EXPECT.search(line)
            if match:
                out[(path.relative_to(repo).as_posix(), lineno)] = [norm(n.strip()) for n in match.group(1).split(",") if n.strip()]
    return out


class Graph:
    def __init__(self, path):
        self.doc = json.loads(path.read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in self.doc["nodes"]}
        self.parent = {e["target_id"]: e["source_id"] for e in self.doc["edges"] if e["type"] == "CONTAINS"}
        self.out = collections.defaultdict(lambda: collections.defaultdict(list))
        self.bases = collections.defaultdict(list)
        for e in self.doc["edges"]:
            if e["type"] in {"CALLS", "MAY_CALL"}:
                self.out[e["source_id"]][e["type"]].append(e["target_id"])
            elif e["type"] == "INHERITS":
                self.bases[e["source_id"]].append(e["target_id"])
        self.sites = collections.defaultdict(list)
        for n in self.doc["nodes"]:
            if n["type"] == "CallSite":
                self.sites[(n["path"], n["range"]["start_line"])].append(n)

    def site(self, key):
        found = self.sites.get(key)
        return max(found, key=lambda n: n["range"]["end_byte"] - n["range"]["start_byte"]) if found else None

    def lineage(self, class_id):
        seen, stack = [], [class_id]
        while stack:
            current = stack.pop()
            if current not in seen:
                seen.append(current)
                stack.extend(self.bases[current])
        return seen

    def names(self, site, kind, expected):
        result = set()
        for target_id in self.out[site["id"]][kind] if site else ():
            target = self.nodes[target_id]
            if target["type"] == "Class":
                ctors = {f"{norm(self.nodes[c]['qualified_name'])}.{m}" for c in self.lineage(target_id) for m in ("__init__", "__new__")}
                hit = ctors & set(expected)
                result |= hit or {norm(target["qualified_name"])}
            else:
                result.add(norm(target["qualified_name"]))
        return result


def load_pycg(path):
    merged = collections.defaultdict(set)
    for key, values in json.loads(path.read_text(encoding="utf-8")).items():
        merged[norm(key)].update(norm(v) for v in values)
    return merged


def pycg_candidates(cg, graph, site):
    if site is None or site["id"] not in graph.parent:
        return set(), set()
    caller = norm(graph.nodes[graph.parent[site["id"]]]["qualified_name"])
    tail = site["properties"]["callee_text"].rsplit(".", 1)[-1]
    callees = {c for c in cg.get(caller, ()) if not c.startswith("<builtin>") and c in cg and any(c.startswith(p) for p in ("cg_cases", "flat_cases", "nsp"))}
    named = set()
    for callee in callees:
        parts = callee.split(".")
        if parts[-1] == tail or (parts[-1] in {"__init__", "__new__"} and len(parts) > 1 and parts[-2] == tail):
            named.add(callee)
    return named, callees


totals = collections.defaultdict(lambda: collections.Counter())
groups = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
details = collections.defaultdict(list)
fn_level = collections.defaultdict(collections.Counter)
kinds = collections.defaultdict(collections.Counter)
no_site = []

for repo_name, source in (("src_repo", "src"), ("flat_repo", ".")):
    repo = CASES / repo_name
    expected = expectations(repo, repo / source)
    static, scip = (Graph(CASES / "out" / f"{repo_name}-{m}.json") for m in ("static", "scip"))
    print(repo_name, "scip resolver", scip.doc["statistics"]["resolver"].get("active"), scip.doc["statistics"]["resolver"].get("status"),
          "may_call static", static.doc["statistics"]["may_call"]["by_match_kind"], "scip", scip.doc["statistics"]["may_call"]["by_match_kind"])
    cg = load_pycg(CASES / "out" / f"{repo_name}-{TOOL}.json")
    for key, exp in expected.items():
        group = re.search(r"g\d\d", key[0]).group(0) + ("-flat" if repo_name == "flat_repo" else "")
        kind = exp[0] if exp in (["external"], ["unknown"]) else "named"
        kinds[group][kind] += 1
        st, sc = static.site(key), scip.site(key)
        if st is None:
            no_site.append((repo_name, key, exp))
        named, callees = pycg_candidates(cg, static, st)
        s_calls, s_may = static.names(st, "CALLS", exp), static.names(st, "MAY_CALL", exp)
        c_calls, c_may = scip.names(sc, "CALLS", exp), scip.names(sc, "MAY_CALL", exp)
        preds = {"static": s_calls, "static+MAY": s_calls | s_may, "scip": c_calls, "scip+MAY": c_calls | c_may, "pycg": named,
                 "scip>pycg": c_calls or named, "scip>pycg>MAY": c_calls or named or c_may}
        for mode, pred in preds.items():
            counter = groups[group][mode]
            if kind == "named":
                tp, fp, fn = len(pred & set(exp)), len(pred - set(exp)), len(set(exp) - pred)
                counter.update(tp=tp, fp=fp, fn=fn)
                if fp or fn:
                    details[mode].append(f"{key[0]}:{key[1]} exp={exp} pred={sorted(pred)}")
            elif pred:
                counter.update({"claim_" + kind: 1, "claim_edges_" + kind: len(pred)})
                details[mode].append(f"{key[0]}:{key[1]} {kind} pred={sorted(pred)}")
        if kind == "named":
            fn_level[group].update(total=len(exp), found=len(set(exp) & callees))

print("no callsite at annotated line:", no_site)
print("\nper group  TP/FP/FN; ext=lines with an internal claim on `external` calls; unk=lines with a claim on `unknown` calls")
print("group      calls(n/e/u) | " + " | ".join(f"{m:>13}" for m in MODES) + " | pycg fn-level")
all_groups = sorted(groups)
for group in all_groups:
    k = kinds[group]
    cells = []
    for mode in MODES:
        c = groups[group][mode]
        extra = "".join([f" e{c['claim_external']}" if c["claim_external"] else "", f" u{c['claim_unknown']}" if c["claim_unknown"] else ""])
        cells.append(f"{c['tp']}/{c['fp']}/{c['fn']}{extra}".rjust(13))
    print(f"{group:10} {k['named']:>3}/{k['external']}/{k['unknown']:<3}    | " + " | ".join(cells) + f" | {fn_level[group]['found']}/{fn_level[group]['total']}")
print()
for mode in MODES:
    c = collections.Counter()
    for group in all_groups:
        c.update(groups[group][mode])
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
    print(f"{mode:15} TP {c['tp']:3} FP {c['fp']:3} FN {c['fn']:3}  P {p:.3f}  R {r:.3f}  external-claims {c['claim_external']} ({c['claim_edges_external']} edges)  unknown-claims {c['claim_unknown']}")
f = collections.Counter()
for group in all_groups:
    f.update(fn_level[group])
print("pycg fn-level found", f["found"], "of", f["total"])
Path(CASES / "out" / "details.txt").write_text("\n".join(f"[{m}] {line}" for m in MODES for line in details[m]), encoding="utf-8")
