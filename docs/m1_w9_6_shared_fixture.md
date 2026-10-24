# M1-W9-6 — Bundle fixture dùng chung cho M2/M3

Ngày23/10/2026. Phạm vi: handoff fixture của tuần9, không repair/model/SWE-bench.
Code/fixture chưa commit hoặc merge; không tự ghi M3 đã nghiệm thu runner.

## 1. Đầu ra và cách sử dụng

Fixture chuẩn: [tests/fixtures/w9_bundle](../tests/fixtures/w9_bundle/README.md).
Recipe: [build_w9_bundle_fixture.py](../scripts/build_w9_bundle_fixture.py).
Tests: [test_w9_bundle.py](../tests/test_w9_bundle.py).

Source được copy nguyên3files từ single_file_login của tuần7–8 lúc bootstrap;
auth.py vẫn `return bool(value)` với CRLF nguyên bản. Hai tests không đổi. Một
bundle gồm4files xuất bởi producer hiện có, không phải dict viết tay hoặc gold.

| Thành phần | Nội dung / tác dụng |
|---|---|
| repo/auth.py, repo/pytest.ini, repo/tests/test_auth.py | Snapshot nhỏ giữ lỗi; không sửa/chạy repair |
| task.json | Issue/expected identity/selectors/scope; paths `repo` và `bundle` tương đối |
| bundle/context.json | 3snippets exact source/ranges, IDs/ranking/counts |
| bundle/context_manifest.json | Graph/source/hash/binding/counter của snapshot |
| bundle/test_links.json | Candidate test links, failing selector và fallback; chưa collection/coverage |
| bundle/repair-context.txt | Bản render tham khảo; consumer tự render từ context đã validate |
| fixture_profile.json | Recipe/static resolver, identity/counter và8file hashes; không tựhash/path máy/timestamp |
| .gitattributes | `* -text` giữ bytes khi clone trênWindows/core.autocrlf=true |
| README.md | Hướng dẫn load/tái tạo, profile fixture và tokenizer riêng, trách nhiệm M2/M3 |

M2/M3 đọc README trước. Lệnh chỉ kiểm handoff, chạy từ rootVGAR với interpreter
đã có dependencies; không cần bậtDocker/WSL hoặc tảiassets:

```powershell
python -B .\scripts\build_w9_bundle_fixture.py --validate-root .\tests\fixtures\w9_bundle
$LASTEXITCODE
```

Mong đợi exit0, JSONstatusPASS/modevalidate/repair_executionNOT_RUN. API hiện có:
`load_task(task.json)` rồi `load_handoff(task, len, 'fixture-only:characters')`.
CLI/helper còn kiểm profile/hash/task consistency; không tự thay đổi source.

## 2. Identity và hai profile

| Thuộc tính | Giá trị thực |
|---|---|
| task_id | w9-single-file-login |
| repo_key / revision | fixture/w9/single-file-login / w9-fixture-v1 |
| graph_version | sha256:1a480ca3a792aa1433747d13818743841e7f4c30beafbd2fe286721a25bdf8cd |
| source_digest | sha256:3121f4240c6e47d67974b4aa550bd8486b53ace95ba478067aa60d876570eedc |
| Source/bundle locations | repo/ và bundle/, resolve theo task.json |
| Fixture counter | len(text), fixture-only:characters;3items,178Unicode characters |
| Optional Qwen counter đã thử | Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554;3items,40snippet tokens |
| Snippet budget | 8000đơn vị theo counter; không phải full-prompt cap6000 |
| Failing selector / fallback | tests/test_auth.py::test_login_rejects_whitespace / tests |
| Admission | trusted_fixture=false; registry không thêm entry |

Consumer hiện có ràng buộc repo/revision/graph/source/counter, **không transport-bind
task_id vào sidecars**. Helper kiểm task/profile hashes và task identity; đây là
consistency check, không phải chữ ký/xác thực chống người sửa đồng thời mọifiles.

Recipe mặc định lấy source từ canonical fixture đã validate khi canonical đã
tồn tại; bootstrap lần đầu mới lấy W78. Điều này tránh CRLF checkout của nguồn
W78 ở máy khác làm thay byte identity fixture W9. Không normalize source để làm
hashPASS. Gitattributes chỉ mới trong W9; W78/code cũ giữ nguyên.

Profile Qwen tạo ra thư mục mới, không thay fixture chuẩn. Assets lấy hoàn toàn
local và được loader hiện có kiểm4hashes/runtime; thiếu/sai sẽ ERROR, không
fallback/network. Tokenizer-mode roundtrip còn có unit tests với synthetic
tiny assets được gắn nhãn fixture/unit-tokenizer, không giả làm Qwen evidence.

## 3. Flow và giới hạn bàn giao

```text
Source snapshot đã khóa bytes + issue/identity đã khai
  → static PythonGraphBuilder
  → SQLite scratch → retrieval (len hoặc verified local tokenizer)
  → create_context_handoff → write_context_handoff
  → task.json + fixture_profile + hashes
  → load_task → load_handoff thật → source/sidecar attestation
  → JSON PASS/metadata; không apply/test/generate
```

M2 dùng bundle này để kiểm consumer boundary; M3 có thể dùng làm đầu vào phát
triển fake runner. **Không gọi fixture này thẳng vào native run_repair rồi kỳ vọng
chạy được**: admission hiện tại chủ động từ chối vì không trusted/registry.
M2-W9-3/4 và integration của M3 là task riêng, không đổiguards trong W9-6.

Fixture chỉ mô phỏng một task, không phải3arms hoặc benchmark. `coverage_verified`
và `collection_verified` vẫnfalse; không chạy failing/regression tests bên trong
repo fixture để báo kết quả repair. Pytest thực thi ở task này là các tests của
producer/consumer/recipe ngoài fixture. Không có reference patch trong context.

## 4. Kiểm thử thực tế và evidence

Evidence: `results/m1/w9/m1-w9-6/20261023-fixture/` (ignored). Mỗi command có argv,
interpreter, UTCstart/end, duration, stdout/stderr, exit và JUnit nếu làpytest.

| Run | Kết quả | Evidence |
|---|---|---|
| RED đầu tiên |34setupERROR vì script chưa tồn tại, không coi là34logicbugs |red.json |
| RED CLI |1FAIL đúng missing recipe |red_cli.json |
| GREEN ban đầu |33PASS/1FAIL: test giả địnhLF trong khi source thậtCRLF |green_precanonical.json |
| GREEN trước bootstrap |33PASS/1SKIP/1deselected; skipoverwrite canonical chưa tồn tại, chưatestcanonical |green_before_bootstrap.json |
| Canonical bootstrap |PASS,3items/178characters |build_canonical.json |
| Full tests M1-W9-6 |40PASS,7,84s; khôngskip/deselect |fixture_suite.json / fixture_suite.junit.xml |
| Selected regression |226PASS,35,25s; gồm40tests mới, không cộng dồn thành266 |selected_regression.json / selected_regression.junit.xml |
| Final verification sau review/docs |226PASS,52,54s;0fail/0error/0skip |final_verification.json / final_verification.junit.xml |
| Ruff0.13.3 thực có |PASS; không gọi đúngpin0.17 qualification |lint.json / versions.json |
| Canonical consumer CLI |PASS, khôngghi fixture |validate_canonical.json |
| Cached Qwen recipe + consumer |PASS40tokens; khôngmodel/inference |qwen_recipe.json / validate_qwen.json |

Selected suite gồm `test_w9_bundle`, `test_m1_handoff`, `test_w9_bm25_handoff`,
`test_w9_pilot_bundles`. Đây **không phải full repository suite**; không chạy
W78 real model, harness, allMCP/rootintegration hoặc swebench. Không có exclusions
trong final selected run. Tokenizer thật ở trên không thay full HF runtime QA.

LỗiCRLF nằm ở giả định của test; đã kiểm rawbytes và chỉnh phép assertion nội
dung, trong khi testpreservation vẫn so nguyênbytes. Không đổi production source
hoặc normalize fixture để vượtguard. Tất cả failures/evidence cũ giữ nguyên.

## 5. Điểm dừng

Sau review và closing checks, ghi trạng thái nghiệm thu kỹ thuật trong statusM1
và PROGRESS. M1-W9-4 vẫnBLOCKED,0campaign/0attempt theo checkpoint riêng. Không
khởi động lại task đó, không taskW9-5, commit/push hoặc Task Status.md.

Closing `close_checks.json` PASS: HEAD/oldsource/tests/config/TaskStatus không
đổi;3files source mới giốngW78 nguyênbytes, hashes/counter/evidence/JUnit đúng,
Gitattributes/Markdownlinks/tables và diffcheckPASS. **M1-W9-6 hoàn thành kỹthuật.**
Mộtminor testimprovement được ghi trong receipt; không cóCritical/Important.
