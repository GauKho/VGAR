# Kế hoạch hoàn tất M2 tuần 7–8 và cải thiện Repair Prompt

> Đã được người dùng duyệt triển khai ngày 14/10/2026 (Asia/Saigon).
> Thực hiện inline với executing-plans và TDD; không commit/push.

**Goal:** ba real repairs PASS với cùng một prompt cuối cùng; source gốc không đổi.
**Architecture:** giữ core M2 độc lập; thêm presentation/prompt V3–V4 và bounded acceptance campaign.
**Tech stack:** Python/core venv hiện có, pinned HF Qwen/CUDA, Git, pytest/mypy/Ruff.
**Spec:** `../../../../New_task/project_plan_16_weeks.md` tuần 7–8 và
`../../../../New_task/2026-10-13-m2-w7-w8-brainstorm-implementation-plan.md`; yêu cầu user phê duyệt trong hội thoại là authority của extension này.

## Scope và nghiệm thu

| Task | Trước triển khai | Gate cuối |
|---|---|---|
| A single_file_login | V1 SEARCH/REPLACE FAIL; V2 hunk counts FAIL | real parse/apply/verify PASS |
| B multi_file_invoice | NOT_RUN | real PASS; sửa cả pricing.py và invoice.py |
| C missing_links | NOT_RUN | real PASS; actual collection/fallback |
| Ba real repairs | Chưa đạt | cả ba cùng version cuối cùng |
| Bàn giao/tái lập | Chưa owner/human xác nhận | tài liệu + evidence + quy trình đồng đội chạy lại |

Đây là gate 3/3 PASS mạnh hơn DoD gốc 3 valid diff + verification.
76 core tests/fake3 đã có, không làm lại implementation. Gate M3/human tách riêng.

## Global constraints

- Chỉ sửa M2_week_7_8; VGAR/old systems/M1 ranking/dirty changes read-only.
- Model Qwen/Qwen3-4B-Instruct-2507 @ cdbee75f17c01a7cc42f958dc650907174af0554, tokenizer và greedy/FP16/autoCUDA không đổi.
- input6000/output1536/reserve256; generation900s/command120s/global1800s.
- Native đúng ba byte-verified fixtures; không external repo, benchmark, train, planner, MCP/API/structural work.
- Không sửa protected tests/config/gold/reference patches/parser/verifier/registry để PASS.
- Một generation/run; tối đa6 NEW attempts,2 failures/campaign; oldV1/V2 evidence bất biến.
- Không output conversion/recount, không best-of-N hoặc fake fallback, không đổi model/resources.

## Review Focus

1. Range end exclusive và blank/EOL/UTF8 phải tạo metadata đúng, source không biến đổi.
2. Metadata/source identity/token budget sai phải chặn trước generation.
3. Resume/pending/PID reuse/concurrency không reset counters hoặc chạy thêm model.
4. Campaign chỉ chốt3 PASS cùng version và đầy đủ gate, không chỉ tin top-level PASS.
5. Final canonical/bundle hashes và immutable profile đúng; không patch ledger để giấu FAIL.

## Milestone 1 — Baseline/pins

- [ ] status/diff/checkpoint/source pin; không quét lại toàn repo.
- [ ] byte snapshots, ba M1 sidecars, tokenizer assets đúng; ghi baseline fingerprints/policy/model.
- [ ] giữ oldfailures; không install/download/modelOK khi profile unchanged.
- [ ] manifest mới sau khi prompt/controller offline đạt.

## Milestone 2 — Prompt/metadata TDD

- [ ] M2 presentation từ validatedDTO, giữ order/snippet/IDs/path/hints. Metadata ngoài code: start/endexclusive/coveredendinclusive/snippetlinecount/fullfilelinecount. Giữ originalM1 text trong evidence.
- [ ] V3 fixed: unifieddiff contract; old=context+removed/new=context+added; không đếm headers/delimiters/presentationnewline; trung tính square(x):returnx→x*x hunk2; checklist path/source/indent/counts/signature/protected/regression/outputonly.
- [ ] V4 fixed trước realV3: V3+neutral2file capped-number/frame-string example và allissueclauses/units/invariants checklist. Không fixtureanswer/percent/strip.
- [ ] giữ V1/V2 template/render, explicitversionmap; internalPolicy thêmV3/V4; PromptArtifact optionalmetadata default, publicDTOs unchanged.
- [ ] RED→GREEN: range1:0-3:0actual2, LFCRLF/blank/noEOL/UTF8partialcols/method/multifile; neutralexamples strictparser; legacyrender; wrongversion/budget; savedrawV2stillreject.
- [ ] fullsuite+Ruff trước inference.

## Milestone 3 — Campaign TDD

- [ ] reserve attempt trước launch, uniqueID/path; pipeline optionalcampaign/attemptkeywords và evidence.
- [ ] durable manifest caps6attempts/2failures; resume không reset; pending kiểm process identity/handle trước, không timeout→dead hoặc auto-rerun.
- [ ] confirmed terminal interruption ERROR consumes slot/failure; runtimeERROR dừng, không promptfixruntime.
- [ ] tests transitions/resume/caps/version isolation/concurrency.

## Milestone 4 — Real runs

V3 A→B→C; nếu đềuPASS chốtV3, không chạyV4. FirstFAIL chuyển fixedV4 và restartA→B→C freshworktree/baseline. Không mangPASSV3 sangV4. SecondFAIL/ERROR hoặccap dừng, khôngV5. Runtime/inputERROR dừng ngay để chẩn đoán.

V3FAILởA/B/C rồi V4ABCpass lần lượt4/5/6attempts. Mỗi attempt lưu toàn bộ prompt/raw/diff/baseline/post/commands/stdoutstderr/exit/tokens/timing/resources/publicbundle/sourceguards. Không unchangedV1/V2rereun.

## Milestone 5 — Review/bàn giao

- [ ] summary tách campaign/task/mode/version, mọiattempt vàfailurecategory.
- [ ] one fresh final reviewer, focusedfixesTDD; fullsuite+Ruff cuối.
- [ ] M2PROGRESS/failures/completion/Vietnameseguide update; latestselector có campaign/task/version/mode.
- [ ] teammate reproduction workflow/evidence riêng; không tự tick human/M3gate.

## Acceptance

3 realruns cùngfinalversion, mỗi run modeldiff tự parse,apply/byteattestation/appliedexport đạt, required+regression/syntax/mypy/Ruff PASS, publicbundle→canonicalhash đúng, original/protected unchanged. B hai file; C actualfallback/collection. Fake/OK không thayreal. Nếu hếtbudget giữBLOCKED đúngnguyênnhân, khôngclaim100%.

4–8 engineeringh estimate;6×1800s globalbudget≈3h+safe finalization, khôngAPIbill nhưng compute/electriccost khác0. Windows3fixturesprototype khôngSWE-bench/held-out capabilityclaim. JUnitcounterminor giữdeferred, không scopecreep.

References: [HF prompting](https://huggingface.co/docs/transformers/main/tasks/prompting), [Git diff](https://git-scm.com/docs/git-diff), [Agentless](https://arxiv.org/abs/2407.01489). Không nhập sampling/ranking/benchmark vào extension.
