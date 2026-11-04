# Results (draft v1) — chỉ số liệu dev

> **Không chứa số held-out.** Mọi số liệu ở đây là trên dev (`configs/m1/w10_dev_manifest.json`, 25 task) và dùng để
> chuẩn bị protocol freeze, không dùng để kết luận. Mỗi bảng có dòng `Nguồn:` (script · record · commit) hoặc
> `Đang chờ:`; `scripts/check_results_sources.py` kiểm tra điều này trong CI.
>
> Thuật ngữ: A0–A3 là **pipeline sinh patch một lượt** (BM25 hoặc graph context, khác nhau ở check bắt buộc của verifier).
> `vgar solve --agent` là **agent bị ràng buộc** (model chọn tool, lúc thử lại và lúc dừng; không đọc code, không tự viết
> diff), chạy trên 5 task và chỉ mô tả. Metric chính: F3, F4, Recall@k, FAR/FRR; resolved (F8) là metric phụ
> (`docs/protocol_freeze_heldout.md` §8).

## 1. Retrieval (R1)

| Arm | N | File R@3 | File R@5 | File R@10 | Function R@5 | File MRR | Δ File R@5 so BM25 [CI95] |
|---|---|---|---|---|---|---|---|
| BM25 | 25 | 0.360 | 0.527 | 0.593 | 0.278 | 0.591 | — |
| Graph (ranking đóng băng `993f02c9…`) | 22 | 0.360 | 0.447 | 0.572 | 0.315 | 0.605 | −0.091 [−0.292, 0.121] |

Nguồn: `scripts/run_bm25_retrieval.py` · `scripts/run_graph_retrieval.py` · `scripts/compare_tune_steps.py` · `results/retrieval/20261013T105428274182Z-5b0743bf6087` · `results/retrieval/20261101T093903486801Z-cfb08e637061` · bảng R1 trong `docs/m1_retrieval_method.md`

Graph có N = 22 vì 3 task sympy timeout ở 300 giây trong mọi run graph. CI95 chứa 0: trên dev chưa đủ bằng chứng
graph khác BM25 về File R@5.

## 2. Repair A0–A2 trên dev (P1, W10)

| Arm | F1 sinh patch | F2 apply strict | F3 áp được | F4 đúng file gold | F5 đúng hàm | F6 test pass | F7 chấp nhận | F8 resolved |
|---|---|---|---|---|---|---|---|---|
| A0 (bm25) | 19 (76%) | 1 (4%) | 5 (20%) | 2 (8%) | 2 (8%) | 0 | 0 | 0 |
| A1 (graph) | 17 (68%) | 1 (4%) | 6 (24%) | 4 (16%) | 4 (16%) | 0 | 0 | 0 |
| A2 (graph + mypy/Ruff) | 16 (64%) | 1 (4%) | 5 (20%) | 4 (16%) | 4 (16%) | 0 | 0 | 0 |

Nguồn: `scripts/run_repair_experiment.py` (aggregate) · experiment `9f1b2346fa028094` + `cfb605118a52b835` · harness `20261029T181203854650Z-cbca03e8ee5d`, `20261030T041825144798Z-015c541f2763` · `docs/status/m3.md` §6.3

N = 25 task mỗi arm (task bị loại vẫn trong mẫu số). A3 và lượt chạy lại A1/A2 sau khi đóng băng ranking: chờ batch
GPU W12 (cần `A3.json`). Không có kiểm định ở đây; kiểm định theo protocol freeze §9 chỉ chạy trên held-out.

## 3. Verifier (V1, V2)

| Arm | Mutant xấu (n) | FAR | Patch tốt (n) | FRR |
|---|---|---|---|---|

Đang chờ: H10, mutant pool (M2-W12-2, M2)

## 4. Impact trên gold patch (I1)

| Phương pháp | N task | F2P đo được | Recall F2P trong vùng | Median số test trong vùng | Median số node trong vùng | Recall file test của test_patch |
|---|---|---|---|---|---|---|

Đang chờ: H5, `scripts/measure_patch_impact.py` chạy trên 25 dev task (M1-X2, M1)

## 5. Graph quality (G1)

| Loại edge | Mẫu gán tay (n) | Precision | Recall | % call site unresolved |
|---|---|---|---|---|

Đang chờ: M1-X1, gán tay edge (M1)

## 6. Incremental update (U1)

| Kịch bản | Cold build (s) | Warm update p50/p95 (s) | Speedup | File đổi | Node bị ảnh hưởng | Cache hit | Trùng full rebuild |
|---|---|---|---|---|---|---|---|

Đang chờ: H5, `scripts/bench_incremental.py` trên `pydata__xarray-4629` (M1-W12-1, M1)

## 7. MCP usability (M1)

| Tool | Số call | p50 (ms) | p95 (ms) | Invalid call rate | Audit completeness | Token/lượt model |
|---|---|---|---|---|---|---|

Đang chờ: M3-X2b, `solve --agent` trên 5 dev task theo `docs/m3_w12_agent_runbook.md` (M3). Khi có số: chỉ mô tả,
N = 5 task, không so sánh thống kê với A0–A3.

## 8. Security (S1)

Bảng S1–S16, mỗi yêu cầu trỏ tới test chứng minh và giới hạn còn lại: `docs/security_checklist.md`.
