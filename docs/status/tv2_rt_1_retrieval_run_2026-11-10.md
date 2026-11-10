# TV2 · RT-1: kết quả retrieval đủ 6 đặc trưng, 10/11/2026

Spec: `docs/superpowers/specs/2026-11-10-tv2-rt-1-retrieval-design.md`. Plan: `docs/superpowers/plans/2026-11-10-tv2-rt-1-retrieval.md`.

## Đã làm

| Phần | Kết quả |
|---|---|
| Cờ mới trong `RetrievalConfig` | `use_component_dependents`, `dependent_symbols_per_component` (3), `may_call_factor` (0,0), `use_trace_component`, `public_api_from_ports`; mặc định tắt |
| Hash | `ranking_config_hash` bỏ qua cờ RT-1 đang ở giá trị tắt; `RetrievalConfig()` vẫn là `sha256:993f02c9…` (`FROZEN_RANKING_HASH`) |
| `components_depending_on` (§4.1) | Từ `DEPENDS_ON` của `G_arch`: symbol trong component phụ thuộc gọi vào component của anchor, tối đa 3 mỗi component, rationale `COMPONENT_DEPENDENT` |
| `MAY_CALL` (§4.2) | Đi như `CALLS` với confidence × `may_call_factor`, không tính vào fan-in |
| `TRACES_TO` (§4.3) | Port của component xếp đầu (confidence ≥ 0,7) làm seed 0,45, rationale `TRACE_COMPONENT` |
| `public_api_risk` (§4.7) | Có Port thì symbol của Port là công khai, không có Port thì dùng `visibility`; trọng số vẫn 0 |
| MCP (§4.6) | `SQLiteGraphService.get_related_context(..., config=None)`; TV1 chọn cấu hình cho tool |
| `RT1_CONFIG` | `RetrievalConfig(may_call_factor=0.5)`, khớp `configs/rt1/rt1_config.json` |
| `recent_change_frequency` (§4.5) | Vẫn "unavailable": checkout và archive không có lịch sử commit; chờ `change_counts` của TV3 (L4-1) |

Công cụ đo: `scripts/materialize_dev_gold.py` (thêm gold cho manifest 50 task từ parquet đã ghim), `scripts/run_rt1_ablation.py` (chạy cuốn chiếu, `--prune`, `--resume`), `scripts/compare_rt1_ablation.py` (bootstrap ghép cặp theo task), `scripts/check_rt1_benchmark.py` (bộ 12 task tự tạo).

## Test

- `tests/test_retrieval_rt1.py` (35 test), `tests/test_rt1_ablation.py` (9), `tests/test_check_rt1_benchmark.py` (2).
- Windows, toàn bộ suite (`-m "not hf and not docker"`, 38 phút): 2967 passed, 29 skipped, 2 xfailed, 3 failed đúng là 3 test đã biết (`tests/m2/w910/test_runner_contract.py::test_different_arm_contexts_can_share_template_without_same_prompt`, `tests/test_official_harness.py::test_campaign_reads_pinned_upstream_run_evaluation_directory`, `tests/test_w9_bundle.py::test_checked_in_fixture_validates_and_matches_recipe`).
- WSL Ubuntu (Python 3.11, `~/.vgar-wsl`): test RT-1 cùng retrieval, trace, dry-run: 165 passed.
- Review cuối (opus): 0 Critical, 4 Important. Đã sửa 3 mục, mỗi mục có test fail trước và pass sau: giới hạn `dependent_symbols_per_component` bị tính theo anchor thay vì theo cặp (component phụ thuộc, component); `--resume` làm rơi task đã ghi artifact nhưng chưa ghi vào `result.json`; `--resume` nhận thư mục tạo bằng cấu hình khác. Mục còn lại (ứng viên từ component phụ thuộc nằm ngoài hạn mức ứng viên của lượt duyệt) giữ theo thiết kế §4.1, có ghi trong docstring; số ứng viên thêm vào tối đa bằng số cặp × 3.
- Chạy thử 3 task làm lộ 2 lỗi của script đo, đã sửa, mỗi lỗi có test fail trước và pass sau: worker của `run_bounded_task` không unpickle được hàm khi script cũ được nạp dưới tên khác; `--prune` bỏ sót file kèm archive tên `<stem>.tar.json`.

## Bộ 12 task tự tạo (spec §6 mục 1b)

`python scripts/check_rt1_benchmark.py <bundle> --out rt1_benchmark.json`, ngân sách 12.000 token.

- Cả 12 task cho cùng kết quả khi chạy hai lần, ở mọi cấu hình.
- Task 05 (`cart-dispatch`, `MAY_CALL` tới 3 lớp) đổi kết quả khi bật `may_call_factor=0.5`; task 02, 10, 11 không đổi.
- Task 01 **không** đổi khi bật `use_component_dependents`: lượt duyệt 2 bước mặc định đã gặp cả 4 hàm của `checkout` gọi `round_vnd` qua cạnh `CALLERS`; cờ chỉ thêm symbol mà lượt duyệt chưa gặp (spec §4.1).
- Task 03, 06, 08, 09 chỉ kiểm cấu hình mặc định (03: không còn cờ tương ứng; 06, 08, 09: issue chưa có traceback dạng `File "...", line N`, chờ sửa repo).
- Task 02, 04, 07, 08, 10, 12 không có file gold trong ứng viên: issue viết tiếng Việt nên không sinh anchor symbol (task 12 cố ý rỗng).

## Chỉnh tham số trên 25/50 task (chỉ dùng để chọn)

25 task của manifest đã đo ở TR-1 (`~/rt1/tune25.txt`). Arm `graph` (chỉ issue), so với `default`, n = 25 (hàm: 24):

| Cấu hình | Recall@5 file | Recall@5 hàm | MRR file (CI95) | Chọn |
|---|---|---|---|---|
| `dependents` | 0 | −0,042 | −0,002 [−0,010; +0,005] | Không (đo lại sau sửa giới hạn theo component, `tune25_dep`: giống hệt ở 3 cột này, MRR hàm −0,002 thay vì −0,004) |
| `may_call_0_5` | 0 | **+0,008** | +0,010 [0,000; +0,026] | **Có** |
| `may_call_1_0` | 0 | 0 | +0,010 [0,000; +0,026] | Không (0,5 tốt hơn) |
| `trace` | −0,020 | −0,083 | +0,025 [−0,009; +0,077] | Không |

Quy tắc chọn (spec §5): Recall@5 file hoặc hàm tăng, và cận trên CI95 của độ chênh MRR file ≥ 0.

```bash
bash wsl_run.sh ~/rt1/tune25.txt ~/rt1/results/tune25      # default + 4 cấu hình, --prune
python scripts/compare_rt1_ablation.py ~/rt1/results/tune25 --arm graph
```

## 50 task: `RT1_CONFIG` so với mặc định

`~/rt1/results/full50/{default,rt1_config}`, 50/50 SUCCEEDED mỗi cấu hình. Ngân sách 12.000 token ([P] 972), bộ đếm dự phòng bytes/4 (`FALLBACK:utf8_bytes_ceil_div4`). Recall@B là `packed_gold_*_in_context` = |C ∩ F\*| / |F\*| ([P] 816).

Arm `graph`:

| Chỉ số | Mặc định | RT-1 | Chênh | CI95 | Tốt hơn / kém đi |
|---|---|---|---|---|---|
| Recall@5 file | 0,743 | 0,723 | −0,020 | [−0,060; 0,000] | 0 / 1 |
| Recall@5 hàm | 0,338 | 0,363 | +0,025 | [0,000; +0,069] | 2 / 0 |
| MRR file | 0,514 | 0,537 | +0,023 | [−0,001; +0,055] | 6 / 1 |
| MRR hàm | 0,253 | 0,270 | +0,017 | [−0,001; +0,044] | 4 / 4 |
| Recall@B file | 0,773 | 0,818 | +0,045 | [0,000; +0,105] | 3 / 0 |
| Recall@B hàm | 0,348 | 0,348 | 0 | [0; 0] | 0 / 0 |

Arm `graph_f2p` (thêm tên test fail): Recall@5 file −0,020, Recall@5 hàm −0,016 [−0,061; +0,012], MRR file +0,020, Recall@B file +0,035 [0; +0,085], Recall@B hàm +0,020 [0; +0,061].

25 task **không** dùng để chỉnh, arm `graph`: Recall@5 file −0,040 [−0,120; 0], Recall@5 hàm +0,040 [0; +0,120], MRR file +0,036 [−0,011; +0,100], Recall@B file +0,050 [0; +0,140].

Thay đổi theo task (arm `graph`): Recall@B file tăng ở `psf__requests-1766`, `sympy__sympy-13031` (0 → 1) và `pylint-dev__pylint-6386` (0 → 0,25); Recall@5 hàm tăng ở `pylint-dev__pylint-7277` (0 → 1) và `sphinx-doc__sphinx-10673` (0,4 → 0,6); Recall@5 file giảm ở `pytest-dev__pytest-7236` (1 → 0).

Nhóm 4 task có traceback đường dẫn tuyệt đối (`astropy__astropy-14309`, `django__django-11087`, `matplotlib__matplotlib-23476`, `psf__requests-1724`): không đổi ở mọi chỉ số.

```bash
python scripts/materialize_dev_gold.py configs/m1/w10_dev_manifest.json ~/w9/dataset/test-00000-of-00001.parquet ~/rt1
bash wsl_run50.sh ~/rt1/all50.txt ~/rt1/results/full50 --resume   # default + rt1_config, --prune
python scripts/compare_rt1_ablation.py ~/rt1/results/full50 --arm graph
python scripts/compare_rt1_ablation.py ~/rt1/results/full50 --arm graph_f2p
```

(`wsl_run.sh`, `wsl_run50.sh` gọi `scripts/run_rt1_ablation.py` với `--config default --config <name>=configs/rt1/<name>.json --budget-tokens 12000 --allow-fallback-counter --prune`.)

## Nhận định

- RT-1 làm đủ việc [plan] dòng 132 giao: 6 đặc trưng và `components_depending_on` chạy thật, đo được từng phần, cấu hình mặc định giữ nguyên.
- Tác dụng trên bộ dev nhỏ: `RT1_CONFIG` tăng Recall@B file (+0,045) và MRR file (+0,023), nhưng mọi CI95 đều chạm 0, và Recall@5 file giảm ở 1 task. Chưa đủ để khẳng định cải thiện; kết luận đúng là "không làm kém đi rõ rệt, cải thiện nhỏ ở Recall@B và MRR".
- Hai cờ không giúp, kèm nguyên nhân thấy trong dữ liệu:
  - `use_component_dependents`: hàm gọi trực tiếp đã nằm trong 2 bước duyệt, nên cờ chỉ thêm symbol xa, đẩy hàm gold xuống.
  - `use_trace_component`: khi hai component bằng điểm (cùng 0,95, cùng `anchor_count`), `rank_component_traces` của TR-1 phân định theo id, nên component ngoài (ví dụ package gốc) thường thắng. Nên sửa thứ tự này ở TR-1 trước khi đo lại cờ.
- `MAY_CALL` được lưu như `CALLS`, nên lượt duyệt từ test fail (arm `graph_f2p`) cũng đi theo các cạnh đoán; vì vậy `failing_test_proximity` ở arm này đổi khi bật `RT1_CONFIG`.
- So sánh với BM25, grep, embedding, file-neighbor, agent default thuộc R1 (tuần 2 ngày 3); R1 dùng lại hai run 50 task ở trên. Run BM25 phải cùng manifest gold, cùng 12.000 token, cùng bộ đếm token.

## Giới hạn

- Manifest chọn với `min1`: 5/50 task sửa từ 2 file nguồn trở lên, trong khi [plan] phụ lục A.3 ghi bộ lọc `min_source_files=2`.
- Bộ 12 task là của TV2; khi nhóm chốt repo mẫu chung ([plan] dòng 470 mục 3), thêm một case RT-1 trên repo đó.
- Bộ đếm token dự phòng bytes/4, không phải tokenizer của model.
- Dung lượng lớn nhất của `~/rt1` khi chạy: 386 MB (3 task), 596 MB (25 task, 5 cấu hình), 1,44 GB (50 task, 2 cấu hình).
- Venv WSL `~/.vgar-wsl` được cài thêm `pyarrow==23.0.1` (đã khai báo trong `pyproject.toml`).
