# M2 Week 5–6 — BM25 & Retrieval Evaluation

Triển khai độc lập tại `D:\Project\CAPSTONES\M2_week_5_6`. Không import hay thay đổi `VGAR`, `vgar_mcp_mvp`, Archify hoặc hệ thống repair đang đóng băng.

Mục đích: làm baseline BM25 trên Python function/code chunks, lấy gold labels từ developer patch và đo retrieval trên SWE-bench. **Đây không phải agent sửa code**: không sinh/apply patch, không chạy test benchmark, không dùng LLM/GPU/Docker.

## Đọc theo thứ tự

Khi lấy project từ nhánh GitHub, đọc [Hướng dẫn bàn giao/clone và tái tạo dữ liệu](docs/GITHUB_HANDOFF.md): gold patches, logs và toàn bộ task artifacts của run bàn giao có trên nhánh; lịch sử kết quả chi tiết được đóng gói ở GitHub Releases. Source cache và `.venv` không được commit.

Nếu cần hiểu cặn kẽ từng yêu cầu, file, thuật ngữ, luồng input/output và cách tự test, đọc [Bản giải thích tổng thể M2 tuần 5–6](GIAI_THICH_M2_W5_W6_VA_CACH_KIEM_THU.md). Tài liệu này phân biệt lệnh setup lần đầu với lệnh chạy lại và phần còn chờ M1.

1. [Hướng dẫn tiếng Việt từ đầu đến cuối](docs/HUONG_DAN_M2_W5_W6.md).
2. [Kế hoạch đã duyệt](docs/IMPLEMENTATION_PLAN.md).
3. [Contract phối hợp với M1/M3](docs/M1_M3_HANDOFF.md).
4. [Tiến độ/checkpoint](PROGRESS.md) — đọc trước khi tiếp tục phiên mới.

## Kết quả hiện tại

- 41 tests PASS; evaluation thật **25/25 task hoàn tất, 0 lỗi**, run cuối 152.95 giây khi đã có cache.
- File Recall@5 = 0.3952; Recall@10 = 0.6152. Function Recall@5 = 0.1095; Recall@10 = 0.1855. Đây là retrieval ranking, không phải repair success.
- [Báo cáo kết quả](results/retrieval/20261001T134641055034Z-5295e04e781d/REPORT.md), [10 inspection cases](docs/INSPECTION_10_TASKS.md), [review và fixes](docs/REVIEW_FINDINGS.md).
- **Chưa đạt toàn bộ DoD chung tuần 5–6**: cần M1 output Graph thật, paired comparison và xác nhận phối hợp/subset M3. Không sửa thêm code BM25 khi chưa có lỗi cụ thể.

## Chạy nhanh — khi venv đã có

```powershell
Set-Location 'D:\Project\CAPSTONES\M2_week_5_6'
# Không cần activate venv hoặc cài lại dependencies mỗi lần.
& '.\.venv\Scripts\python.exe' '.\scripts\record_tests.py'
# Dùng manifest cố định đã được tạo, không chọn lại task theo kết quả.
& '.\.venv\Scripts\python.exe' '.\scripts\run_evaluation.py' --manifest '.\data\manifests\verified-c104f840cc67-25.json' --offline
```

`--offline` chỉ dùng khi archives của tất cả task đã được tải; lần đầu bỏ flag đó. Mỗi lần chạy tạo thư mục mới trong `results`; không ghi đè lần trước.

## Thành phần

| Đường dẫn | Công dụng |
|---|---|
| `src/m2_retrieval/chunks.py` | AST entity extraction, decorator/nested/method, code windows, source hash |
| `src/m2_retrieval/bm25.py` | Code tokenizer, inverted index BM25, context budget |
| `src/m2_retrieval/gold_labels.py` | Unified diff → changed source file/function labels và disposition |
| `src/m2_retrieval/metrics.py` | Recall@k, MRR, all-gold coverage, denominator |
| `src/m2_retrieval/dataset.py` | Pin HF revision, khóa manifest, source commit archive cache |
| `src/m2_retrieval/evaluation.py` | Pipeline tuần tự, hash-bound resume, per-task evidence |
| `src/m2_retrieval/m1_adapter.py` | ContextPayload adapter và paired comparison dùng output thật |
| `src/m2_retrieval/evidence.py` | JSON recorder, UUID, atomic write, full stdout/stderr |
| `src/m2_retrieval/report.py` | Bảng kết quả từ artifacts, không giả số liệu Graph |
| `scripts/` | Entry points có `--help`, không cần cài VGAR |
| `tests/` | Unit/integration tests với source, patch, tar archive và resume thật |
| `data/manifests/` | Manifest 25 task + dataset revision + query/patch hashes |
| `data/gold/patches/` | Gold developer patch, chỉ dùng offline evaluation |
| `data/repositories/archives/` | Source tar.gz tại SHA cố định + provenance sidecar |
| `results/tests/<run_id>/result.json` | Command/stdout/stderr/exit/duration/hash của mỗi lần test |
| `results/retrieval/<run_id>/` | Summary, từng task, context, gold labels, M1 requests |
| `results/comparison/<run_id>/` | Paired Graph vs BM25 hoặc trạng thái thiếu M1 |

## Tính trung thực của kết quả

- Dataset: SWE-bench Verified test snapshot `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`.
- Manifest pilot chọn trước ranking: 25 task, round-robin repository, `instance_id` tăng dần; **chưa phải manifest chung M3**.
- Tiêu chí multi-file: developer patch thay đổi ≥2 file nguồn `.py`, không phải test/docs. Snapshot này có 70 task đạt tiêu chí của script, không coi 70 là hằng số mọi snapshot/định nghĩa.
- Source đọc từ commit archive HTTPS: kiểm tra SHA trong URL/root tar, archive SHA256, source/corpus hashes. **Không tuyên bố kiểm chứng cryptographic Git object/tree hash**.
- Token cost dùng estimator `ceil(UTF-8 bytes/4)`, không phải tokenizer LLM/billing token. Không có API cost.
- Gold chỉ là changed-code proxy, không phải toàn bộ context cần sửa. Added-only function/file không tồn tại trong base phải báo riêng; unmapped functions không được score như bộ nhãn hoàn chỉnh.
- M1 W3–4 chưa có graph retrieval W5–6. Adapter đã có nhưng **DoD Graph vs BM25 chưa đạt** cho đến khi có export thật trên cùng 25 task.

## Nguồn

[SWE-bench datasets chính thức](https://www.swebench.com/SWE-bench/guides/datasets/), [SWE-bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified), [BM25 — Stanford IR book](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html).
