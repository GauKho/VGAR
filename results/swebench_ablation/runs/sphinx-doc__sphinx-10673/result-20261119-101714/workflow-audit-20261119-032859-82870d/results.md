# Sphinx-10673 — A5 agent result, 19/11/2026

**Patch resolved; workflow A5 PARTIAL.** Đây là lượt DeepSeek qua 9Router mới, không phải lượt Big Pickle diagnostic trước đó.

Session: `ses_e0e553f18ffefL00HA9HRdMW8C`.
Model: `9router/oc/deepseek-v4.1-flash-free`.
Patch SHA-256: `81ee3defd13f206839e946beedcb3faefd0683f00bad640b4848688cf69b9040`.

## Kết quả và binding của đúng diff cuối

| Phép đo | Kết quả |
|---|---|
| SWE-bench official resolved | **true** |
| Patch successfully applied | true |
| FAIL_TO_PASS | **1 PASS, 0 FAIL** |
| PASS_TO_PASS | **9 PASS, 0 FAIL** |
| Grading process | Exit0; 29.102ms; không gọi model |
| Final public test/semantic call | PASS; đúng diff đã grading; admitted/applied once/executed/cleaned |
| Public semantic contracts | **5/5 PASS** |
| Likely invariants | **408 learned, 0 violations**, python-fallback; Daikon không cấu hình |
| Final impact | PASS; hash input khớp diff cuối |
| Graph verification | **ERROR** cả3lần; worker timeout khoảng115–117s; exit-9; cleanupPASS |
| Ranking | Tool PASS ở lần3, nhưng **eligible=false**, score0,15; không được xem là ACCEPT |
| Retrieval | **PARTIAL**: 4anchor calls lỗi; context có1serverPASS nhưng JSON text trong session không parse đầy đủ |

Giữ riêng hai kết luận: SWE-bench xác nhận patch sửa đúng issue; verifier của VGAR chưa hoàn tất graph checks. Không lấy official resolved để sửa graph ERROR thành PASS hoặc vượt required checks.

## Agent đã thực sự dùng MCP

| Tool | Lượt gọi trực tiếp trong session | Kết quả đáng chú ý |
|---|---:|---|
| search_symbols | 2 | 2PASS |
| build_or_update_graph | 1 | PASS; view có G_repo/G_task/G_arch/G_code |
| find_task_anchors | 4 | 4hosttoolERROR; issue không byte-identical với1333ký tự gốc (hai input1288ký tự,hai input83ký tự/chỉtitle) |
| get_related_context | 2 | 1hosttoolERROR;1serverPASS, client JSON text không parse được đầy đủ |
| analyze_patch_impact | 8 | 4ERROR do diff input chưa hợp lệ;4PASS; lần cuối hash khớp patch graded |
| run_relevant_tests | 3 | 3PASS; lần cuối hash và combined semantic evidence khớp |
| verify_patch_graph_constraints | 3 | 3ERROR_TIMEOUT trên đúng diff cuối |
| rank_patch_candidates | 3 | 2INVALID_ARGUMENT;1PASS nhưng candidate ineligible |

Tổng26MCPattempts trực tiếp;21terminal records trong server audit. Năm hosttoolERROR trước envelope không có request ID để ghép server record. Mọi request ID lấy được từ envelope đều khớp audit đúng run/task/snapshot. Ba execution audit records không có trường arm; armA5 được đối chiếu qua pinned descriptor/config hash và response binding, không tự sửa raw log. JSONL audit hợp lệ, không trộn task/run. Đây là local logs, không phải attestation mật mã chống native agent sửa file.

## Metric của session

| Metric | Giá trị |
|---|---:|
| Input Tokens | 531.493 |
| Output Tokens | 42.221 |
| Reasoning Tokens | 50.824 |
| Cache Read Tokens | 10.301.824 |
| Cache Write Tokens | 0 |
| Tool calls toàn session | 156 |
| MCP calls trực tiếp | 26 |
| Model steps hoàn tất | 135 |
| Compaction | 1 |
| Session busy→idle | **2.090.588ms ≈34phút50,6giây** |
| Host-reported cost | 0; không xác minh hóa đơn thực |
| HTTP Requests | Không được export;135steps không phải135HTTPrequests |

Thời gian trên lấy từ metadata busy→idle của UI, có tool waits và có thể có thời gian tương tác của người dùng. Không đồng nhất với stopwatch CLI của A0–A4 cũ hoặc29,102giây grading. Token/cost là host-reported, không tự cộng reasoning/cache thành billing totals. Metadata session outcome=succeeded dù verifier có timeout: đó là hai cấp trạng thái khác nhau.

## Giới hạn và bước tiếp theo

Lượt này dùng đúng model DeepSeek mong muốn và thực sự gọi MCP, nên không mang nhãn BigPickle/model-mismatch. Tuy nhiên, giữ nhãn **exploratory / workflow partial**: local Web Search policy khác pilotA0–A4, semantic contracts được soạn sau pilot, graph checks chưa hoàn tất. Chưa phải nghiệm thu A5 đầy đủ hoặc hoàn thành matrix10task×6arm. Không suy ra cải thiện hiệu quả từ một task/một attempt.

Agent có lệnh tạo tempvenv và pip install -e .[test]; đây là dependency setup của workspace hiện tại, không phải bằng chứng tải lời giải. Việc này góp vào thời gian/chi phí agent, còn official grading dùng image ghim độc lập. Scan command hạn chế không chứng minh native-agent sandbox/network isolation.

Không chạy lại agent/test hoặc sửa rawresults trong audit này. Hai việc cần xử lý trước khi tuyên bố workflow đầy đủ: payload/binding anchor và timeout worker graph checker. Giữ required checks/timeout hiện có; không waive hoặc chuyển ERROR thành PASS.

## Evidence

- `../grading-20261119-032244-a0e951/official-report.json`, `result-summary.json`: verdict chính thức.
- `audit.json`: metric, call records, final-hash matching và limitations.
- `server-audit.jsonl`: bản copy audit nguyên gốc của đúng run.
- `final-combined-semantic.json`: evidence5contracts/408invariants của đúng candidate.
- `worker-receipts.json`:3timeout receipts, bounded cleanupPASS.
- `source-hashes.json`: fingerprints của patch/session/binding/audit/officialreports.

Original user inputs và mọi report lịch sử giữ nguyên. Không commit/push.
