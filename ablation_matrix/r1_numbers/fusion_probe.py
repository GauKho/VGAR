"""Offline probe: fuse existing R1 ranked lists (read-only). Not a repo change."""
import glob, json, sys, statistics

TASKS = sorted(glob.glob(sys.argv[1] + "/tasks/*.json"))
FUNC_KINDS = {"function", "method"}


def lists(arm):
    files, funcs = [], []
    for r in arm["ranked"]:
        if r["path"] not in files:
            files.append(r["path"])
        fid = r.get("function_id")
        if r["kind"] in FUNC_KINDS and fid and fid not in funcs:
            funcs.append(fid)
    return files, funcs


def recall(ranked, gold, k):
    return len(set(ranked[:k]) & gold) / len(gold) if gold else None


def mrr(ranked, gold):
    for i, x in enumerate(ranked, 1):
        if x in gold:
            return 1 / i
    return 0.0


def rrf(rank_lists, weights, k=60):
    score = {}
    for lst, w in zip(rank_lists, weights):
        for i, x in enumerate(lst, 1):
            score[x] = score.get(x, 0) + w / (k + i)
    return sorted(score, key=lambda x: (-score[x], x))


def funcs_only_graph(arm):
    # graph ranking with Class/File/Module items dropped (granularity fix)
    return lists(arm)[1]


CONFIGS = {
    "bm25": lambda a: lists(a["bm25"]),
    "neighbor": lambda a: lists(a["neighbor"]),
    "graph(rt1)": lambda a: lists(a["task_trace_rt1"]),
    "RRF graph+bm25": lambda a: tuple(rrf([lists(a["task_trace_rt1"])[i], lists(a["bm25"])[i]], [1, 1]) for i in (0, 1)),
    "RRF graph+neighbor": lambda a: tuple(rrf([lists(a["task_trace_rt1"])[i], lists(a["neighbor"])[i]], [1, 1]) for i in (0, 1)),
    "RRF graph+bm25+neighbor": lambda a: tuple(rrf([lists(a[n])[i] for n in ("task_trace_rt1", "bm25", "neighbor")], [1, 1, 1]) for i in (0, 1)),
}

rows = {name: {"fR@1": [], "fR@5": [], "fnR@5": [], "fnR@10": [], "fnMRR": []} for name in CONFIGS}
check = []
for path in TASKS:
    d = json.load(open(path))
    gf, gfn = set(d["gold"]["gold_files"]), set(d["gold"]["gold_functions"])
    a = d["arms"]
    # sanity: my file recall@5 vs stored metric for bm25
    check.append(abs(recall(lists(a["bm25"])[0], gf, 5) - a["bm25"]["metrics"]["file_recall@5"]) < 1e-9)
    for name, fn in CONFIGS.items():
        files, funcs = fn(a)
        rows[name]["fR@1"].append(recall(files, gf, 1))
        rows[name]["fR@5"].append(recall(files, gf, 5))
        if gfn:
            rows[name]["fnR@5"].append(recall(funcs, gfn, 5))
            rows[name]["fnR@10"].append(recall(funcs, gfn, 10))
            rows[name]["fnMRR"].append(mrr(funcs, gfn))

print(f"tasks={len(TASKS)} sanity file@5 matches stored bm25 metric: {sum(check)}/{len(check)}")
print(f"{'config':26s}" + "".join(f"{m:>8s}" for m in rows["bm25"]))
for name, r in rows.items():
    print(f"{name:26s}" + "".join(f"{statistics.mean(v):8.3f}" for v in r.values()))

import random
def ci(a, b, n=2000, seed=0):
    rnd = random.Random(seed); diffs = [x - y for x, y in zip(a, b)]
    boots = sorted(statistics.mean(rnd.choices(diffs, k=len(diffs))) for _ in range(n))
    return statistics.mean(diffs), boots[int(.025 * n)], boots[int(.975 * n)]
for cand in ("RRF graph+bm25", "RRF graph+bm25+neighbor"):
    for base in ("bm25", "neighbor", "graph(rt1)"):
        for m in ("fnR@5", "fnMRR", "fR@1"):
            d, lo, hi = ci(rows[cand][m], rows[base][m])
            print(f"{cand:24s} - {base:10s} {m:6s} {d:+.3f} [{lo:+.3f}; {hi:+.3f}]")

print("--- does graph add anything over text-only fusion? ---")
text = {"fR@1": [], "fR@5": [], "fnR@5": [], "fnMRR": []}
multi = []
for path in TASKS:
    d = json.load(open(path)); a = d["arms"]
    gf, gfn = set(d["gold"]["gold_files"]), set(d["gold"]["gold_functions"])
    files, funcs = (rrf([lists(a[n])[i] for n in ("bm25", "neighbor")], [1, 1]) for i in (0, 1))
    text["fR@1"].append(recall(files, gf, 1)); text["fR@5"].append(recall(files, gf, 5))
    if gfn:
        text["fnR@5"].append(recall(funcs, gfn, 5)); text["fnMRR"].append(mrr(funcs, gfn))
    multi.append(len(gf) > 1 or len(gfn) > 1)
print("RRF bm25+neighbor        " + "  ".join(f"{m} {statistics.mean(v):.3f}" for m, v in text.items()))
for m in ("fR@1", "fR@5", "fnR@5", "fnMRR"):
    d_, lo, hi = ci(rows["RRF graph+bm25+neighbor"][m], text[m])
    print(f"3-way - text-only {m:6s} {d_:+.3f} [{lo:+.3f}; {hi:+.3f}]")
print("tasks with >1 gold file or function:", sum(multi), "/", len(multi))
