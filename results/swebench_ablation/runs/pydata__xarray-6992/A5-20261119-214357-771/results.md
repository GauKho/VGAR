# Xarray-6992 — kết quả A5

**SWE-bench: UNRESOLVED.** Patch áp dụng thành công; harness exit 0. Đây là kết quả chấm patch, không phải lỗi khởi chạy harness.

| Task | Arm | Resolved | FAIL_TO_PASS đạt / tổng | PASS_TO_PASS đạt / tổng |
|---|---|---|---:|---:|
| pydata__xarray-6992 | A5 | false | 0 / 12 | 945 / 945 |

Patch đã lưu chỉ thay một dòng trong xarray/core/dataset.py. Các test official còn thất bại gồm reset_index của DataArray/Dataset, các tổ hợp drop/convert và groupby_drops_nans. Không sửa patch sau grading.

| Metric | Giá trị host ghi nhận |
|---|---:|
| Input tokens | 170,817 |
| Output tokens | 5,958 |
| Reasoning tokens | 10,892 |
| Cache read tokens (ghi riêng) | 1,848,832 |
| Tool calls | 41 |
| MCP calls / audit server | 17 / 17 |
| Model steps hoàn tất | 26 |
| UI busy→idle | 976,995 ms (~16,28 phút) |
| Grading riêng | 66,667 ms |
| Host-reported cost | 0 USD |

Không đồng nhất UI busy→idle với stopwatch CLI. Input/cache là các trường riêng của host; HTTP Requests không được expose. Chi phí thực tế chưa được xác minh độc lập.

| Bằng chứng MCP | Kết quả |
|---|---|
| Anchors/context trước sửa code | PASS; bản đầy đủ đã đối chiếu audit |
| Impact với diff cuối | PASS, binding/hash khớp |
| Tests/semantic với diff cuối | PASS trong scope public được cấp |
| Graph verification với diff cuối | PASS |
| Ranking diff cuối | eligible=true, score=0.65 trong scope public/graph/semantic |
| Lệch trình tự prompt | search_symbols chỉ gọi sau lần edit đầu tiên |

Năm public contracts: 5/5 PASS. Invariants dùng python-fallback, không phải Daikon. Public test admission dùng sentinel; các kết quả này không thay thế bộ test official.
Sự khác biệt PASS nội bộ / FAIL official cho thấy coverage public hiện tại không đủ phân biệt patch này; không được báo resolved dựa trên ranking/semantic PASS.

Lần đọc audit đầu đã hiểu sai JSON bị OpenCode cắt ngắn là tool failure. Kết luận đó bị thay thế: đã đọc các full tool output từ cache host, kiểm request IDs với server audit và hash evidence. Những attempt audit cũ được giữ làm lịch sử parser, không phải kết quả chạy model khác.

Evidence:
- Official report: `grading-20261119-144855-89eb09/official-report.json`
- Audit có thẩm quyền: `workflow-audit-20261119-145308-15bb64/audit.json`
- `evaluation-summary.json`, `results.csv`, `candidate.diff`, `session.json`.
- Candidate SHA-256: `sha256:115b7d93853506cfe1bf6b13ab24f3703e103136cafe1b89d28fab56fd7047c4`

Model: 9router/oc/deepseek-v4.1-flash-free. Grading/audit không gọi model và không tự retry agent. Đây mới là A5 của một task, chưa phải toàn bộ ablation matrix.
