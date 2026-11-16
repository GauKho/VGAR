import json, glob, os, statistics as s
B = os.path.expanduser("~/rt1/results")
ARMS = ["bm25","grep","neighbor","no_task_trace","task_trace","a3","ast_no_task_trace","arch_no_task_trace","task_trace_rt1"]
def load(r): return [json.load(open(f)) for f in sorted(glob.glob(f"{B}/{r}/tasks/*.json"))]
def mean(data, a, k):
    v = [t["arms"][a]["metrics"].get(k) for t in data]
    v = [x for x in v if x is not None]
    return (s.mean(v), len(v)) if v else (None, 0)
def f(x, d=3): return "—" if x is None else (f"{x:,.0f}".replace(",", ".") if abs(x) >= 100 else f"{x:.{d}f}".replace(".", ","))
data = load("r1_50")
groups = [
 ("A. File (recall@k)", ["file_recall@1","file_recall@3","file_recall@5","file_recall@10","file_recall@20","file_mrr"]),
 ("B. Hàm (recall@k)", ["function_recall@1","function_recall@3","function_recall@5","function_recall@10","function_recall@20","function_mrr"]),
 ("C. Acc@k kiểu LocAgent (đủ mọi gold trong top-k)", ["file_all_gold@1","file_all_gold@5","file_all_gold@10","function_all_gold@1","function_all_gold@5","function_all_gold@10"]),
 ("D. Component", ["component_recall@1","component_recall@3","component_recall@5","component_mrr"]),
 ("E. Trong ngân sách 12.000 token (Recall@B)", ["packed_gold_file_in_context","packed_gold_function_in_context","packed_all_gold_files_in_context","packed_all_gold_functions_in_context","packed_tokens_to_first_gold_file","packed_tokens_to_first_gold_function"]),
 ("F. Chi phí / chẩn đoán", ["context_tokens","packed_items_packed","rank_items","anchor_count","file_reach","function_reach","retrieve_seconds"]),
]
for title, keys in groups:
    print(f"\n### {title}\n")
    print("| Cấu hình | " + " | ".join(keys) + " |")
    print("|---" * (len(keys)+1) + "|")
    for a in ARMS:
        print(f"| {a} | " + " | ".join(f(mean(data,a,k)[0]) for k in keys) + " |")
print("\nn function-gold tasks:", mean(data,"bm25","function_recall@5")[1])
