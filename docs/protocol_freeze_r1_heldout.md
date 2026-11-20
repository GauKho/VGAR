# Protocol freeze: R1 retrieval trên held-out (TV2)

> **Bản nháp, 17/11/2026.** File chỉ có hiệu lực khi cả nhóm duyệt và người dùng tạo annotated tag `protocol-freeze-r1`
> trên commit chứa file này. Sau tag, `heldout_gate` so file trong working tree với nội dung tại tag; mọi thay đổi phải
> là amendment kèm tag `protocol-freeze-r1-amend-<n>`.
> Spec: `docs/superpowers/specs/2026-11-17-tv2-g1-embedding-r1-heldout-design.md` §3. File freeze của repair
> (`docs/protocol_freeze_heldout.md`, tag `protocol-freeze`) là protocol khác và không bị file này ảnh hưởng.

**Nguồn.** Proposal không nói tới held-out, freeze hay kiểm định thống kê; nó chỉ yêu cầu số benchmark có "nguồn và protocol
đo lại" (dòng 1490). Quy trình dev rồi held-out lấy từ plan 2 tuần ([test] mục 3, dòng 382: "freeze protocol rồi chạy
held-out đúng một lần"). Metric lấy từ proposal §13.2 (dòng 1311–1317). Bootstrap và Holm là lựa chọn của nhóm ([mm] 1.4:
phần thống kê là "suy luận, proposal không định nghĩa").

## 1. Những gì đã xem trước khi freeze

Mọi lựa chọn dưới đây dựa trên **50 task dev** (`configs/m1/w10_dev_manifest.json`, có gold:
`~/rt1/data/manifests/w10-dev-50-gold.json`). Chưa ai mở, chạy hay tune trên held-out; lần đọc held-out duy nhất là
`count_heldout_eligible.py` (chỉ đếm, không in nội dung; `results/heldout_access.log`).

| Lượt dev | Dùng để |
|---|---|
| `r1_50` | 9 cấu hình, chọn `RT1_CONFIG`, giữ layer tắt |
| `r1_full50_noflag`, `r1_full50` | thử bật layer và cờ: không có lợi, build chậm khoảng 19 lần → tắt |
| `r1_emb50_t1024` | cánh embedding (50/50); 9 cấu hình cũ trùng hoàn toàn `r1_50` |
| `r1_emb50` | **bỏ**: code cũ để độ dài 8192 token, hết bộ nhớ GPU, chỉ 15/50 task chạy được |

Kết quả trộn RRF được chọn **sau khi** xem dev (16/11), nên chỉ là kết quả phụ (mục 6).

## 2. Commit và môi trường

| Mục | Giá trị |
|---|---|
| Commit | Commit có tag `protocol-freeze-r1`. Commit này phải chứa thay đổi `--embedding-max-tokens` / `--embedding-batch-size` của `ablation_matrix/embedding_baseline.py` và `run_r1_ablation.py` (hiện chưa commit trong checkout chính) |
| `builder_hash` | `sha256:7af65aa5b6bd7c545fe0bb7594df56e7ca17715cc750688f137fef86d8f7923b` (của `r1_emb50_t1024`). Lượt held-out phải ra cùng giá trị; khác thì dừng |
| Máy | WSL Ubuntu, GPU NVIDIA GeForce RTX 4050 Laptop |
| Python và gói | Python 3.11.17 (`~/.vgar-wsl`), torch 2.5.1+cu121, sentence-transformers 5.7.0, transformers 4.57.6 |
| Code chạy | Bản sao của repo tại đúng commit có tag (không dùng bản sao cũ `~/vgar-rt1`) |

## 3. Dataset và task

| Mục | Giá trị |
|---|---|
| Dataset | `princeton-nlp/SWE-bench_Verified`, revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a` |
| Parquet | `sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd` (`~/w9/dataset/test-00000-of-00001.parquet`) |
| Chia split | `sha256_instance_id_first8hex_mod100_lt40_dev_v1`: 208 dev / 292 held-out |
| Truy vấn | `problem_statement_only_no_hints_or_gold` |
| Lọc task (D3-1) | **ĐỀ XUẤT (a): cả 292 task, `--min-source-files 1`**, giống cách chọn dev (`selection_policy` của manifest dev có `min1`). Phương án (b) chỉ giữ 42 task có patch gold sửa ≥ 2 file: quá ít để phát hiện chênh lệch. Nhóm xác nhận trước khi ký |
| Gold | File và hàm trong patch gold (`data/gold/patches/`), bỏ file test; `F*_approx` cho frontier |

## 4. Cấu hình (cánh)

| Cánh | Mô tả |
|---|---|
| `bm25`, `grep`, `neighbor` | Baseline văn bản |
| `embedding` | `nomic-ai/CodeRankEmbed`, revision `3c4b60807d71f79b43f3c4363786d9493691f8b1`, tiền tố truy vấn `Represent this query for searching relevant code: `, `max_tokens` 1024, batch 8 |
| `no_task_trace` (A1), `task_trace` (A2), `a3`, `ast_no_task_trace`, `arch_no_task_trace` | Graph, như báo cáo R1 |
| `task_trace_rt1` | A2 + `RT1_CONFIG` = `RetrievalConfig(may_call_factor=0.5)`, `ranking_config_hash` = `sha256:d3e6933772781ab664efdad583d308874a07fc9106c82fa89796886065137712` |

- Layer (tree-sitter-graph, SCIP, LSP, JARVIS, Joern) và các cờ: **tắt**.
- Ngân sách context 12.000 token; đếm token `FALLBACK:utf8_bytes_ceil_div4` (`--allow-fallback-counter`).
- Lịch sử commit: `--history none`.

## 5. Kết quả chính (đăng ký trước)

Đúng với `PRIMARY_PAIRS` và `PRIMARY_METRICS` trong `ablation_matrix/run_r1_ablation.py`.

| Cặp (ứng viên − nền) | Câu hỏi |
|---|---|
| `task_trace_rt1 − bm25` | Graph phục vụ so với baseline §13.1 (RQ2, M2) |
| `task_trace_rt1 − embedding` | như trên |
| `task_trace_rt1 − grep` | như trên |
| `task_trace − no_task_trace` | Tác dụng của task trace (A2 − A1) |

Metric (proposal §13.2): `file_recall@1`, `file_recall@5`, `function_recall@5`, `function_mrr`,
`packed_gold_function_in_context` (Recall@B hàm), `packed_frontier_in_context` (`dependency_frontier_recall@B` theo `F*_approx`).

Thống kê: chênh lệch ghép cặp theo task; CI95 bootstrap 2.000 lần, seed 0; p hai phía bằng bootstrap
(`fusion.bootstrap_p`, không bao giờ bằng 0); hiệu chỉnh **Holm** trên cả họ 4 cặp × 6 metric = 24 kiểm định.
Kết luận "có khác biệt" chỉ khi `p_holm < 0,05`. Hàm metric chỉ tính trên task có hàm gold.

Với 292 task, chênh lệch nhỏ nhất phát hiện được khoảng 0,041 (hàm R@5), 0,047 (hàm MRR), 0,058 (file R@1)
(báo cáo R1, mục 5).

## 6. Kết quả phụ và mô tả (không dùng để trả lời RQ2)

- Các cặp còn lại trong `PAIRS` (A1 so với từng baseline, A3 − A2, AST-only, kiến trúc, RT1 − A2): báo cáo CI, không p, không Holm.
- **RRF** (`ablation_matrix/fusion.py`, k = 60, trọng số bằng nhau, trộn danh sách top-100 đã lưu): `rrf_graph_bm25_neighbor`,
  `rrf_bm25_neighbor`, `rrf_graph_embedding`, `rrf_embedding_bm25`; hai cặp `FUSION_PAIRS`. Ghi là "phân tích thêm ngoài
  proposal", chọn sau khi xem dev.
- **ĐỀ XUẤT, nhóm quyết:** Hit@k và Acc@k kiểu bài báo (`ablation_matrix/paper_metrics.py`) tính trên cùng danh sách xếp hạng,
  chỉ để so với CoSIL Table III (`docs/status/tv2_r1_paper_comparison_2026-11-17.md`). Nếu giữ dòng này thì script phải nằm
  trong commit có tag. Nếu bỏ thì không được thêm sau khi đã xem held-out.
- Component recall, `context_tokens` và các metric còn lại trong `METRICS`: mô tả.

## 7. Quy trình chạy

Sau tag, trong WSL (`R` là bản sao repo tại commit có tag):

```bash
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/prepare_manifest.py ~/rt1 --split heldout --allow-heldout --protocol r1 \
  --count 292 --min-source-files 1 --revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/<manifest held-out> \
  --out ~/rt1/results/r1_heldout --allow-heldout --allow-fallback-counter --prune \
  --embedding-model nomic-ai/CodeRankEmbed --embedding-revision 3c4b60807d71f79b43f3c4363786d9493691f8b1 \
  --embedding-max-tokens 1024 --embedding-batch-size 8 --embedding-cache ~/rt1/emb_cache | tee ~/rt1/r1_heldout.log
```

1. Manifest held-out tạo **sau** tag; `prepare_manifest.py` gắn `freeze_sha256` của file này vào manifest.
2. Chạy **đúng một lượt**, attached, không chạy lượt nặng khác cùng lúc (WSL 7,8 GB RAM). Ước tính khoảng 7,5 giờ cho phần
   graph và văn bản, cộng phần embedding.
3. Nếu bị ngắt: chạy lại cùng lệnh với `--resume`. Task lỗi do hạ tầng (hết bộ nhớ, ngắt WSL, lỗi mạng) được chạy lại đúng
   task đó trên cùng commit và ghi vào báo cáo. Không đổi cấu hình, không bỏ task vì kết quả xấu.
4. Task lỗi do code thì giữ nguyên là lỗi trong kết quả và báo cáo số task lỗi.

## 8. Báo cáo

`docs/status/tv2_r1_heldout_<ngày>.md`: bảng mục 5 với `mean_delta`, CI95, `p`, `p_holm`; bảng mục 6; số task thành công/lỗi;
`builder_hash`, `manifest_hash`, tag và commit; mỗi số kèm lệnh tái tạo. Số dev chỉ được nhắc làm bối cảnh, không gộp với held-out.

## 9. Ký duyệt

| Thành viên | Vai trò | Duyệt |
|---|---|---|
| TV1 | MCP host, ablation agent | ĐANG CHỜ |
| TV2 | Graph, retrieval (R1) | ĐANG CHỜ |
| TV3 | Verification | ĐANG CHỜ |
