"""Spike: can PyCG's function-level call graph be attached to VGAR CallSites, and does it agree with SCIP?

args: <pycg.json> <graph.json (static or scip)>
"""
import collections
import json
import sys

raw = json.load(open(sys.argv[1], encoding="utf-8"))
print("raw keys with backslash", sum("\\" in k for k in raw), "of", len(raw))
merged = collections.defaultdict(set)
for key, values in raw.items():  # On Windows PyCG names a module both a\b and a.b; merge the two identities.
    merged[key.replace("\\", ".")].update(v.replace("\\", ".") for v in values)
cg = {key: sorted(values) for key, values in merged.items()}
doc = json.load(open(sys.argv[2], encoding="utf-8"))
nodes = {n["id"]: n for n in doc["nodes"]}
callables = [n for n in doc["nodes"] if n["type"] in {"Function", "Method", "Test"}]
by_qn = collections.defaultdict(list)
for n in callables:
    by_qn[n["qualified_name"]].append(n)
module_qns = {n["qualified_name"] for n in doc["nodes"] if n["type"] == "Module"}
class_qns = {n["qualified_name"] for n in doc["nodes"] if n["type"] == "Class"}
parent = {e["target_id"]: e["source_id"] for e in doc["edges"] if e["type"] == "CONTAINS"}
calls_of = collections.defaultdict(list)
for e in doc["edges"]:
    if e["type"] == "CALLS":
        calls_of[e["source_id"]].append(e["target_id"])

print("graph", doc["statistics"]["resolver"].get("active"), "callables", len(callables), "classes", len(class_qns), "modules", len(module_qns))
print("pycg keys", len(cg), "edges", sum(map(len, cg.values())))
kinds = collections.Counter()
for key in cg:
    kinds["builtin" if key.startswith("<builtin>") else "callable" if key in by_qn else "module" if key in module_qns
          else "class" if key in class_qns else "other"] += 1
print("pycg key kinds", dict(kinds))
print("other keys sample", [k for k in cg if not k.startswith("<builtin>") and k not in by_qn and k not in module_qns and k not in class_qns][:12])
internal = [(a, b) for a, vals in cg.items() for b in vals if a in by_qn and (b in by_qn or b in class_qns)]
print("edges caller+callee both in graph", len(internal))
ext = collections.Counter("builtin" if b.startswith("<builtin>") else "external/other" for a, vals in cg.items() for b in vals if not (b in by_qn or b in class_qns))
print("edges whose callee is not in graph", dict(ext))

# Function-level agreement with the graph's CALLS.
graph_pairs = set()
for call_id, targets in calls_of.items():
    caller = parent.get(call_id)
    if caller in nodes:
        for t in targets:
            graph_pairs.add((nodes[caller]["qualified_name"], nodes[t]["qualified_name"]))
pycg_pairs = set(internal)
print("function-level pairs: graph", len(graph_pairs), "pycg", len(pycg_pairs), "both", len(graph_pairs & pycg_pairs),
      "graph only", len(graph_pairs - pycg_pairs), "pycg only", len(pycg_pairs - graph_pairs))


def short(qn):
    return qn.rsplit(".", 1)[-1]


def candidates_for(call):
    caller = parent.get(call["id"])
    if caller not in nodes:
        return None
    tail = call["properties"]["callee_text"].rsplit(".", 1)[-1]
    out = set()
    for callee in cg.get(nodes[caller]["qualified_name"], ()):
        if callee.startswith("<builtin>"):
            continue
        if callee in by_qn or callee in class_qns:
            name = short(callee)
            if name == tail or (name in {"__init__", "__new__"} and callee.rsplit(".", 2)[-2] == tail):
                out.add(callee)
    return out


sites = [n for n in doc["nodes"] if n["type"] == "CallSite"]
unresolved = [n for n in sites if n["id"] not in calls_of]
resolved = [n for n in sites if n["id"] in calls_of]
bucket = collections.Counter()
for call in unresolved:
    c = candidates_for(call)
    bucket["caller not found" if c is None else "0" if not c else "1" if len(c) == 1 else "2+"] += 1
print("unresolved callsites", len(unresolved), "pycg candidates by same-name match", dict(bucket))

# Agreement proxy: on callsites the graph resolved, does PyCG name the same target?
agree = collections.Counter()
for call in resolved:
    c = candidates_for(call)
    targets = {nodes[t]["qualified_name"] for t in calls_of[call["id"]]}
    ctor = {f"{t}.__init__" for t in targets} | {f"{t}.__new__" for t in targets}
    if c is None or not c:
        agree["pycg silent"] += 1
    elif len(c) == 1:
        agree["unique, same target" if c & (targets | ctor) else "unique, different target"] += 1
    else:
        agree["several, includes target" if c & (targets | ctor) else "several, misses target"] += 1
print("resolved callsites", len(resolved), dict(agree))

# How many calls in one function share a tail name (site ambiguity when mapping a function-level edge).
same_tail = collections.Counter()
per = collections.Counter()
for call in sites:
    per[(parent.get(call["id"]), call["properties"]["callee_text"].rsplit(".", 1)[-1])] += 1
for count in per.values():
    same_tail["1" if count == 1 else "2+"] += 1
print("(caller, tail name) groups", dict(same_tail))
