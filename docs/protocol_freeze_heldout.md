# Protocol freeze: đánh giá held-out (VGAR-MCP)

> **Bản nháp.** Chỉ có hiệu lực sau khi cả ba thành viên approve PR chứa file này và có annotated tag
> `protocol-freeze` trên commit merge. Sau tag, mọi thay đổi là amendment (§12).
> Spec: `docs/superpowers/specs/2026-11-03-m3-w12-design.md` §4. Ô `ĐANG CHỜ` phải được điền trước khi ký.

**Quyết định trước khi xem held-out.** Mọi lựa chọn dưới đây dựa trên dev (25 task, `configs/m1/w10_dev_manifest.json`).
Không ai trong nhóm đã chạy, tune hay sửa prompt dựa trên held-out. `dataset.py` từ chối mở held-out khi chưa có tag
(§6) và ghi log mỗi lần mở vào `results/heldout_access.log`.

## 1. Commit và môi trường

| Mục | Giá trị |
|---|---|
| Commit code | ĐANG CHỜ: commit được tag `protocol-freeze`. Batch held-out chạy đúng commit này |
| Máy chạy | WSL Ubuntu trên máy GPU của M3 |
| Python | ĐANG CHỜ: phiên bản của `~/vgar/.venv` |

## 2. Model và prompt

| Mục | Giá trị |
|---|---|
| Model | ĐANG CHỜ (D12): `model_id` và revision SHA của Qwen đã pin |
| Tokenizer manifest | ĐANG CHỜ: sha256 của `artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json` |
| Prompt | ĐANG CHỜ: `prompt_version` và sha256 template |
| Seed sinh | ĐANG CHỜ: seed (hoặc ghi "greedy, không có seed") |

## 3. Variants

| Variant | Arm | `required_checks` | File + sha256 | `policy_hash` |
|---|---|---|---|---|
| A0 | bm25 | tests | `configs/m2/variants/A0.json` · ĐANG CHỜ | ĐANG CHỜ |
| A1 | graph | tests | `configs/m2/variants/A1.json` · ĐANG CHỜ | ĐANG CHỜ |
| A2 | graph | tests, syntax, mypy, ruff | `configs/m2/variants/A2.json` · ĐANG CHỜ | ĐANG CHỜ |
| A3 | graph | A2 + api, structural | ĐANG CHỜ (M2-W12-1, `A3.json`) | ĐANG CHỜ |

Fairness: A1 chỉ khác A0 ở arm; A2 chỉ khác A1 ở `required_checks`; A3 chỉ khác A2 ở `required_checks` (V12).

## 4. Budget và timeout

| Mục | Giá trị |
|---|---|
| Token budget context | ĐANG CHỜ: theo `configs/m1/w9_bundle_profile_repair.json` |
| Timeout sinh patch, timeout lệnh | ĐANG CHỜ (H8, M2-X2). Nếu không có đề xuất: giữ timeout W10 và ghi confound timeout ở arm graph (D26) là threat |
| Số lần thử lại | ĐANG CHỜ: theo `repair_config` |

## 5. Retrieval

- Config ranking đóng băng: `sha256:993f02c962dde7b1d506497798b44bcc4316ed5b5d64a9c84c5ab2a296bbb14a`
  (giá trị mặc định của `RetrievalConfig`, ghim trong `tests/test_graph_retrieval.py`).
- Resolver: static, `source_roots` mặc định của builder. k của Recall@k: ĐANG CHỜ, theo `docs/m1_retrieval_method.md`.

## 6. Dataset

| Mục | Giá trị |
|---|---|
| Nguồn | SWE-bench Verified, parquet `sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd` |
| Chia split | `sha256_instance_id_first8hex_mod100_lt40_dev_v1` (dev 40%, held-out 60%, theo `instance_id`) |
| Manifest held-out | ĐANG CHỜ: tạo **sau** tag bằng `scripts/prepare_manifest.py --split heldout --allow-heldout`; manifest mang `freeze_sha256` của file này |
| N held-out và cách chọn | ĐANG CHỜ: N, `--min-source-files`, thứ tự chọn |
| Cổng truy cập | `require_split` chỉ cho mở held-out khi có tag, file này không đổi sau tag, và `freeze_sha256` của manifest khớp |

## 7. Harness

- Profile harness: ĐANG CHỜ (`configs/m1/w10_harness_profile.json` + sha256).
- Image Docker: ĐANG CHỜ: digest image của từng task.

## 8. Metric

Chốt 03/11/2026 dựa trên dev. Lý do: resolved rate là 0/25 ở mọi arm nên không phân biệt được arm nào.

| Loại | Metric | Định nghĩa |
|---|---|---|
| Chính | F3 | Patch cuối cùng áp được vào source |
| Chính | F4 | Patch đã áp sửa ít nhất một file nguồn mà gold patch sửa |
| Chính | Recall@k | Tỉ lệ file gold có trong top-k context của retrieval |
| Chính | FAR / FRR | Trên mutant pool: mutant xấu được verifier chấp nhận / patch tốt bị từ chối |
| Phụ | Resolved (F8) | Verifier chấp nhận và harness chính thức chấm `RESOLVED` |

F1, F2, F5, F6, F7 chỉ báo cáo mô tả. A2 vs A1 và A3 vs A2 đổi check của verifier nên tác động trực tiếp lên FAR/FRR;
F3/F4 chỉ đổi gián tiếp qua feedback lượt thử lại.

## 9. Phép thống kê

Ba phép so sánh có chủ đích (chốt 03/11/2026); không so cả 6 cặp:

| So sánh | Câu hỏi | Phép thống kê |
|---|---|---|
| A1 vs A0 | Context từ graph có hơn BM25 không? | McNemar exact, ghép cặp theo task |
| A2 vs A1 | Bắt buộc syntax, mypy, ruff khi verify có giúp không? | McNemar exact, ghép cặp theo task |
| A3 vs A2 | Thêm API/structural check có giúp không? | McNemar exact, ghép cặp theo task |
| Retrieval graph vs BM25 | Recall@k | Bootstrap CI 95% ghép cặp cho hiệu số, 10.000 lần lấy mẫu lại theo task, seed cố định |

- McNemar bản exact (nhị thức, hai phía), báo cáo kèm b và c. FAR/FRR ghép cặp theo từng patch của mutant pool.
- Holm trong nhóm 3 phép so sánh của mỗi metric chính, α = 0,05 cho cả nhóm.
- Metric phụ chỉ báo cáo mô tả kèm b, c. Phép so sánh ngoài danh sách là khám phá, không đăng ký trước.
- Sức mạnh: ĐANG CHỜ: N held-out và hiệu ứng tối thiểu phát hiện được (MDE) ở α = 0,05, power 0,8 cho từng metric chính.
- Khi không có ý nghĩa: viết "không đủ bằng chứng về khác biệt", không viết "tương đương".

## 10. Lệnh chạy

ĐANG CHỜ (H7): chép từ `heldout_commands.md` của lần dry-run M1-W12-2 đã PASS, thay `<HELDOUT_MANIFEST>` bằng
manifest held-out ở §6.

## 11. Chữ ký

| Vai trò | Tên | Ngày | Link review PR |
|---|---|---|---|
| M1 | | | |
| M2 | | | |
| M3 | | | |

## 12. Amendment

Mọi thay đổi sau tag: thêm mục "Amendment n" dưới đây bằng PR mới, ghi lý do, ngày, và **đã nhìn thấy kết quả
held-out nào chưa**. Gắn tag `protocol-freeze-amend-<n>`; cổng ở §6 dùng tag amend mới nhất.

(Chưa có amendment.)
