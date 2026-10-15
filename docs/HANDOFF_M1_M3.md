# Handoff M1 → M2 → M3

## Standalone gate đã nghiệm thu ngày 15/10/2026

A/B/C đều PASS trong ba runs mới cùng V11/core r002, không feedback; raw model tự
parse/apply, requiredFAIL→PASS/regression/static/cleanup/source/bundle PASS.
Không đổi public DTO hoặc pipeline runtime trong final validation. Báo cáo:
`NGHIEM_THU_FINAL_A_B_C_V11_R002.md`; manifest/evidence ở
`results/final_acceptance/2026-10-15-v11-r002`.
M3 MCP transport/integrated loop và teammate reproduction vẫn là external gates,
chưa được xác nhận thay owner. Final profile không phải default config/demo.json.

## Đã chốt bởi người dùng

- Plan M2 đã duyệt ngày14/10. Independent package; VGAR nguồn chỉ đọc.
- HF Qwen3-4B @ cdbee75f17c01a7cc42f958dc650907174af0554 cho prototype;
  Native chỉ ba fixture tin cậy. Không gộp thành benchmark Qwen32B/vLLM.
- Counter M1 kiểm snippets; M2 đếm full chat prompt. Profile input6000,
  output1536, reserve256, một candidate/run.
- Interface M1: `receive_context_handoff` trước model, `diagnose_changed_paths`
  từ actual diff paths trên snapshot gốc; collect/run trên worktree sau patch.
- Tests/config bảo vệ; mapping thiếu/limited dùng approved scope `tests`;
  required missing/skip/xfail/incomplete không PASS.

## Python entry point M3 có thể bọc sau review

`vgar_m2_w78.pipeline.run_repair(task, policy, generator, executor, output_root,
m1_counter=..., tokenizer=..., profile=...)` trả RunHandle với `.path`,
`.directory`, `.record`. Hiện Native do pipeline sở hữu lease; `executor`
external bị từ chối cho đến khi có adapter được duyệt. Không truyền arbitrary
repo root, shell command hoặc interpreter từ LLM.

Shared public DTOs không đổi. Nội bộ chi tiết hơn ở canonical JSON;
`EvidenceBundle.verification.api_check/structural_check` giữ NOT_RUN.
MCP tool schemas/transport thuộc M3, chưa sửa/tích hợp tại VGAR.

## Inputs đã có

`examples/tasks/<case>.json`: approved task/source identity (không suy lại từ
manifest). `examples/snapshots/<case>/`: source gốc. `examples/handoffs/<case>/`:
ba sidecars M1 và producer text tham khảo; M2 render lại text đã kiểm.
`examples/inputs_receipt.json`: hashes/provenance/source M1 run ngày14/10.

Không upload `tests/fixtures/reference_patches` vào prompt/endpoint. Files này
chỉ dành cho FakeGenerator hoặc test engine; real không đọc chúng.

## Gates tách riêng

Core offline, real invocation, real standalone repair, M1 source/consumer,
M3 MCP integration và human reproduction là các gate khác nhau. M1 handoff
PASS không đồng nghĩa model sửa được. Reviewer/teammate cần lưu xác nhận riêng;
agent không ký thay M1/M3 hoặc người đã chạy lại.

