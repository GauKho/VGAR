"""Read-only: recompute R1 ranked lists under paper metric definitions.

Hit@k  (CoSIL Top-N, ARISE R@k): >=1 gold item in top k.
Acc@k  (LocAgent/Agentless): all gold items in top k.
MRR    : 1/rank of first gold item (0 if absent from top-100).
"""
import glob, json, random, statistics, sys

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


def rrf(rank_lists, k=60):
    score = {}
    for lst in rank_lists:
        for i, x in enumerate(lst, 1):
            score[x] = score.get(x, 0) + 1 / (k + i)
    return sorted(score, key=lambda x: (-score[x], x))


def fused(a, names):
    return tuple(rrf([lists(a[n])[i] for n in names]) for i in (0, 1))


CONFIGS = {n: (lambda n: lambda a: lists(a[n]))(n) for n in
           ("bm25", "neighbor", "no_task_trace", "task_trace", "task_trace_rt1")}
CONFIGS["RRF bm25+neighbor"] = lambda a: fused(a, ("bm25", "neighbor"))
CONFIGS["RRF rt1+bm25+neighbor"] = lambda a: fused(a, ("task_trace_rt1", "bm25", "neighbor"))

hit = lambda r, g, k: float(bool(set(r[:k]) & g))
acc = lambda r, g, k: float(g <= set(r[:k]))


def mrr(r, g):
    return next((1 / i for i, x in enumerate(r, 1) if x in g), 0.0)


METRICS = {
    "F_Hit@1": ("f", lambda r, g: hit(r, g, 1)), "F_Hit@3": ("f", lambda r, g: hit(r, g, 3)),
    "F_Hit@5": ("f", lambda r, g: hit(r, g, 5)), "F_MRR": ("f", mrr),
    "Fn_Hit@1": ("fn", lambda r, g: hit(r, g, 1)), "Fn_Hit@3": ("fn", lambda r, g: hit(r, g, 3)),
    "Fn_Hit@5": ("fn", lambda r, g: hit(r, g, 5)), "Fn_MRR": ("fn", mrr),
    "F_Acc@1": ("f", lambda r, g: acc(r, g, 1)), "F_Acc@3": ("f", lambda r, g: acc(r, g, 3)),
    "F_Acc@5": ("f", lambda r, g: acc(r, g, 5)),
    "Fn_Acc@5": ("fn", lambda r, g: acc(r, g, 5)), "Fn_Acc@10": ("fn", lambda r, g: acc(r, g, 10)),
}

vals = {c: {m: [] for m in METRICS} for c in CONFIGS}
for p in TASKS:
    d = json.load(open(p))
    gf, gfn = set(d["gold"]["gold_files"]), set(d["gold"]["gold_functions"])
    for c, fn in CONFIGS.items():
        files, funcs = fn(d["arms"])
        for m, (lvl, f) in METRICS.items():
            if lvl == "f":
                vals[c][m].append(f(files, gf))
            elif gfn:  # LocAgent: drop tasks with no modified function
                vals[c][m].append(f(funcs, gfn))


def ci(v, n=2000, seed=0):
    rnd = random.Random(seed)
    b = sorted(statistics.mean(rnd.choices(v, k=len(v))) for _ in range(n))
    return b[int(.025 * n)], b[int(.975 * n)]


print("n tasks:", len(TASKS), "| n with function gold:", len(vals["bm25"]["Fn_Hit@1"]))
for m in METRICS:
    print(f"\n{m}")
    for c in CONFIGS:
        v = vals[c][m]
        lo, hi = ci(v)
        print(f"  {c:24s} {statistics.mean(v):.3f} [{lo:.3f}; {hi:.3f}]")
