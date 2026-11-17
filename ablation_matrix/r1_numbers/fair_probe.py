"""Read-only checks on R1 results: multi-file counts, test-file filter fairness, power."""
import glob, json, math, os, random, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fusion_probe import lists, recall, mrr, rrf, TASKS  # noqa: E402  (re-runs probe output; ignore)

TEST = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_tests?\.py$|(^|/)conftest\.py$")


def drop_tests(arm):
    keep = [r for r in arm["ranked"] if not TEST.search(r["path"])]
    return lists({"ranked": keep})


def ci(diffs, n=2000, seed=0):
    rnd = random.Random(seed)
    boots = sorted(statistics.mean(rnd.choices(diffs, k=len(diffs))) for _ in range(n))
    return statistics.mean(diffs), boots[int(.025 * n)], boots[int(.975 * n)]


multi_file = multi_func = 0
test_in_top5 = []
rows = {k: {"fR@1": [], "fR@5": [], "fnR@5": [], "fnMRR": []} for k in
        ("bm25", "bm25-notest", "neighbor", "neighbor-notest", "text RRF", "text RRF notest",
         "3way", "3way notest")}
for path in TASKS:
    d = json.load(open(path)); a = d["arms"]
    gf, gfn = set(d["gold"]["gold_files"]), set(d["gold"]["gold_functions"])
    multi_file += len(gf) > 1; multi_func += len(gfn) > 1
    test_in_top5.append(sum(bool(TEST.search(p)) for p in lists(a["bm25"])[0][:5]))
    L = {"bm25": lists(a["bm25"]), "bm25-notest": drop_tests(a["bm25"]),
         "neighbor": lists(a["neighbor"]), "neighbor-notest": drop_tests(a["neighbor"]),
         "graph": lists(a["task_trace_rt1"])}
    fuse = lambda names: tuple(rrf([L[n][i] for n in names], [1] * len(names)) for i in (0, 1))
    L["text RRF"] = fuse(["bm25", "neighbor"]); L["text RRF notest"] = fuse(["bm25-notest", "neighbor-notest"])
    L["3way"] = fuse(["graph", "bm25", "neighbor"]); L["3way notest"] = fuse(["graph", "bm25-notest", "neighbor-notest"])
    for k in rows:
        files, funcs = L[k]
        rows[k]["fR@1"].append(recall(files, gf, 1)); rows[k]["fR@5"].append(recall(files, gf, 5))
        if gfn:
            rows[k]["fnR@5"].append(recall(funcs, gfn, 5)); rows[k]["fnMRR"].append(mrr(funcs, gfn))

print("\n=== fair_probe ===")
print(f"gold >1 file: {multi_file}/50 ; gold >1 function: {multi_func}/50")
print(f"bm25 top-5 files that are tests: mean {statistics.mean(test_in_top5):.2f}, tasks with any: {sum(x>0 for x in test_in_top5)}")
for k, r in rows.items():
    print(f"{k:18s}" + "  ".join(f"{m} {statistics.mean(v):.3f}" for m, v in r.items()))
for m in ("fR@1", "fnR@5", "fnMRR"):
    d_, lo, hi = ci([x - y for x, y in zip(rows["3way notest"][m], rows["text RRF notest"][m])])
    sd = statistics.stdev([x - y for x, y in zip(rows["3way notest"][m], rows["text RRF notest"][m])])
    need = lambda mde: math.ceil(((1.96 + 0.84) * sd / mde) ** 2)
    print(f"graph contribution (test-filtered text) {m:6s} {d_:+.3f} [{lo:+.3f}; {hi:+.3f}]  sd={sd:.3f}  n80%@MDE.05={need(.05)}  @.10={need(.10)}")
