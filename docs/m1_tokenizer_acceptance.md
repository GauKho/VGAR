# M1 — nghiệm thu tokenizer và snippet budget

Ngày 03/10/2026. Người dùng duyệt Qwen/Qwen3-4B-Instruct-2507, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, budget **8000 token cho snippets**
và thư mục lưu dưới VGAR. Milestone 3 hoàn tất phần triển khai và nghiệm thu
standalone M1; chất lượng retrieval thuộc Milestone 4, tích hợp M2/M3 bàn giao riêng.

## Cấu hình và file thực tế

- Tokenizer ở `D:/KLTN/VGAR/artifacts/m1/tokenizers/Qwen3-4B-Instruct-2507/cdbee75f17c01a7cc42f958dc650907174af0554/`.
- Chỉ có tokenizer.json, tokenizer_config.json, vocab.json, merges.txt, tổng
  **15.880.703 bytes**. Không tải model weights/Torch/Transformers.
- Provisioner kiểm pinned upstream metadata và LFS SHA256/git blob identity;
  [tokenizer manifest](../artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json)
  lưu source URLs, revision, sizes và SHA256. assets_directory tương đối với manifest
  để có thể provision cùng cấu trúc ở máy khác.
- tokenizer.json SHA256: `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`.
- Runtime `tokenizers==0.22.1` cài riêng tại `D:/KLTN/M1/tokenizer-runtime`,
  không đổi dependencies của model/agent M3. Chỉ import runtime này khi dùng counter.
- M1 LocalTokenizerCounter kiểm hashes trước khi nạp chính bytes đã kiểm, không
  download khi retrieve. Tắt saved truncation/padding; encode từng snippet với
  add_special_tokens=false. Literal special-token strings trong source vẫn được đếm.
- Shared ContextPayload không thêm field. Counter revision/hash/runtime nằm trong
  M1 diagnostics sidecar với `--explain` và acceptance manifest.
- File tokenizer tải về được .gitignore loại khỏi Git; manifest và bằng chứng nhỏ
  vẫn có thể review/version control. Chưa commit/push.

## Kết quả nghiệm thu

**95/95 M1 tests đạt, không skip**: [log](../artifacts/m1/tokenizer-acceptance/tests.txt).
Gồm 86 tests baseline trước đó và 9 tests mới về tokenizer/provisioning/CLI.
Đã sửa CLI M1 xuất UTF-8 khi stdout bị redirect trên Windows; kiểm thử có source Unicode.

Snapshot VGAR mới, no-Jedi: **4021 nodes, 5188 edges**, 108 file Python,
partial_file_count=0. Số lượng tăng gồm code/tests mới; không phải đo chất lượng graph.
[Acceptance manifest](../artifacts/m1/tokenizer-acceptance/manifest.json) lưu graph
version/hash, source hashes, runtime provenance và các kết quả sau:

| Synthetic task | Candidates | Snippets | Actual tokens / budget | Truncated |
|---|---:|---:|---:|---|
| Builder nested scope | 70 | 46 | 7950 / 8000 | true |
| Context path validator | 34 | 26 | 7295 / 8000 | true |
| No anchor | 0 | 0 | 0 / 8000 | false |

Đối chiếu từng snippet bằng native tokenizer encode độc lập, kiểm sum ≤budget;
API và CLI trả cùng kết quả khi dùng cùng task/input. Case Unicode + CRLF có
snippet **14 token**: budget 14 pack nguyên snippet, budget 13 bỏ snippet và
truncated=true. Empty text, literal special tokens và text dài cũng khớp native counts.
Source/base graph giữ nguyên trong lượt nghiệm thu; shared contracts và ba Context
JSON schemas giữ nguyên. [Scope audit](../artifacts/m1/tokenizer-acceptance/scope_audit.json)
xác nhận không sửa/thêm/xóa code riêng M2/M3 trong working tree đã kiểm.

## Chạy lại

Từ `D:/KLTN/VGAR`, provision tokenizer một lần khi có mạng:

```powershell
& 'D:/KLTN/M1/.venv-win/Scripts/python.exe' -m pip install `
  --target 'D:/KLTN/M1/tokenizer-runtime' --no-deps `
  -r scripts/requirements_m1_tokenizer.txt
& 'D:/KLTN/M1/.venv-win/Scripts/python.exe' scripts/provision_m1_tokenizer.py `
  --model-id 'Qwen/Qwen3-4B-Instruct-2507' `
  --revision cdbee75f17c01a7cc42f958dc650907174af0554 `
  --assets-root artifacts/m1/tokenizers `
  --manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json
```

Sau đó counter/retrieval chạy local, không cần mạng:

```powershell
$env:PYTHONPATH = 'D:/KLTN/M1/tokenizer-runtime'
& 'D:/KLTN/M1/.venv-win/Scripts/python.exe' scripts/run_m1_tests.py
& 'D:/KLTN/M1/.venv-win/Scripts/python.exe' scripts/accept_m1_tokenizer.py `
  --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json `
  --graph-output 'D:/KLTN/reports/vgar_m1_20261003/graph_m1_tokenizer_no_jedi.json' `
  --output-directory artifacts/m1/tokenizer-acceptance
& 'D:/KLTN/M1/.venv-win/Scripts/python.exe' scripts/get_related_context.py `
  'D:/KLTN/reports/vgar_m1_20261003/graph_m1_tokenizer_no_jedi.json' . `
  --budget-tokens 8000 --tokenizer-manifest artifacts/m1/tokenizer-acceptance/tokenizer_manifest.json `
  --issue-text 'src/vgar/graph/builder.py:93 has a nested scope bug' --explain
```

Nếu source Python đổi, dựng snapshot mới trước retrieval. Nếu thiếu runtime,
tests tokenizer là optional/skip; không dùng lượt đó thay bằng chứng 95/95 hiện tại.

## Phần tiếp theo

- Milestone 4: dev tasks/gold annotations, Graph-vs-BM25, Recall@3/5/10, MRR,
  actual snippet token cost và latency theo protocol được review. Các task trên
  là synthetic, không phải SWE-bench hay bằng chứng repair success.
- M3 vẫn load model/tokenizer theo ID với revision=null trong config. Cần M3
  đồng bộ revision và phân bổ wrapper/instructions/issue/chat-template/response
  reserve trước nghiệm thu end-to-end; 8000 không phải tổng prompt budget.
- M2/M3 consumer sign-off, MCP exposure/repair integration chưa thực hiện ở scope M1.
  History/component features còn các giới hạn trong retrieval method.
