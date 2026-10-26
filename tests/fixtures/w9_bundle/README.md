# M1-W9-6 — Fixture bàn giao cho M2/M3

## Mục đích và dữ liệu

Đây là fixture contract nhỏ, không phải task SWE-bench hoặc kết quả sửa lỗi.
Source ban đầu được copy nguyên bytes từ single_file_login của tuần7–8.
auth.py vẫn dùng `return bool(value)`: tên chỉ có khoảng trắng còn được chấp nhận.
Hai tests vẫn ở trạng thái đầu vào, không được sửa/chạy repair trong task này.

- repo/: snapshot nhỏ riêng; auth.py là file được phép sửa nếu admission được
  cấp trong task khác. tests/ và pytest.ini được bảo vệ.
- task.json: issue, selectors, expected identity; paths tương đối với file này.
- bundle/: context.json, context_manifest.json, test_links.json và bản render
  repair-context.txt. Consumer tự render lại, không tin bản render producer.
- fixture_profile.json: counter/recipe/source identity và hashes của task,
  source, sidecars; không tự hash profile, không có path máy hoặc timestamp.
- .gitattributes: giữ nguyên bytes khi Git checkout, tránh CRLF làm lệch hashes.

Một bundle dùng chung, không có nhãn benchmark graph/BM25 hoặc A0/A1/A2.
Graph dùng static resolver, không khởi chạy SCIP/LSP; database chỉ ở scratch.
Snippet budget8000 là đơn vị counter của profile, không phải full-prompt cap.

## Cách load và kiểm consumer thật

Từ repository VGAR, dùng Python đã có dependencies của VGAR. Không cài lại nếu
máy đã sẵn sàng. Lệnh sau chỉ đọc fixture và gọi consumer, không chạy model/tests:

```powershell
python -B .\scripts\build_w9_bundle_fixture.py --validate-root .\tests\fixtures\w9_bundle
```

Output JSON phải có status=PASS, mode=validate, task_id, counter_label và
source_digest. Exit0 chỉ xác nhận handoff hợp lệ; exit1 có traceback stderr.

Ví dụ dùng API hiện có sau khi đặt PYTHONPATH=src tại repo root:

```python
from pathlib import Path
from vgar.repair.config import load_task
from vgar.repair.context_adapter import load_handoff

task = load_task(Path('tests/fixtures/w9_bundle/task.json'))
handoff = load_handoff(task, len, 'fixture-only:characters')
print(handoff.context_text)
print(handoff.inputs)
handoff.assert_unchanged()
```

Để kiểm cả fixture_profile/task/source/sidecar hashes, dùng CLI --validate-root
hoặc helper load_fixture trong script. Consumer kiểm repo/revision/graph/source
và counter; task_id chỉ là consumer metadata, không được transport-bind trong
sidecars hiện tại. Helper kiểm thêm task/profile consistency, không phải cơ chế
chứng thực chữ ký hoặc admission cho dữ liệu không tin cậy.

## Tái tạo deterministic, không ghi đè

Từ repo root, chọn thư mục output mới chưa tồn tại:

```powershell
$out = Join-Path '.\results\m1\w9\m1-w9-6' ('rebuild-' + [guid]::NewGuid().ToString('N'))
python -B .\scripts\build_w9_bundle_fixture.py --output-root $out
python -B .\scripts\build_w9_bundle_fixture.py --validate-root $out
```

Script copy source từ canonical repo/ đã khóa bytes khi fixture chuẩn đã tồn
tại; bootstrap đầu tiên mới lấy từ fixture W78. Cùng source/profile/producer
cho kết quả byte-identical. Không copy cache, weights, Git, venv hoặc DB.
Output đã tồn tại hoặc chồng lên fixture bảo vệ bị chặn; không có --overwrite.

## Counter fixture và tokenizer thật là hai profile khác nhau

Mặc định dùng len(text), nhãn fixture-only:characters: số Unicode characters,
không phải số bytes, số token Qwen hoặc phép đếm full chat. CI không cần assets.
Không đưa counter này vào CLI production rồi gọi đó là tokenizer thật.

Khi M3 cần fake runner có tokenizer profile thật, tạo bộ output RIÊNG bằng
manifest local đã pin; không thay bundle fixture-counter chuẩn:

```powershell
$out = Join-Path '.\results\m1\w9\m1-w9-6' ('qwen-rebuild-' + [guid]::NewGuid().ToString('N'))
$manifest = '.\artifacts\m1\tokenizer-acceptance\tokenizer_manifest.json'
python -B .\scripts\build_w9_bundle_fixture.py --output-root $out --tokenizer-manifest $manifest
python -B .\scripts\build_w9_bundle_fixture.py --validate-root $out --tokenizer-manifest $manifest
```

Manifest phải có đúng4assets/hash và runtime tokenizers tương thích theo loader
hiện tại. Không tải assets/weights/mạng; thiếu/sai phải ERROR, không fallback.
M2/M3 phải dùng counter/tokenizer tương ứng với bundle đã chọn. Cùng len-counter
không đủ chứng minh full prompt của HF phù hợp budget hoặc runtime chạy được.

## Giới hạn và trách nhiệm tiếp theo

- load_handoff PASS không là pytest collection/coverage/repair PASS. Metadata
  collection_verified và coverage_verified vẫn false; test hints là candidates.
- trusted_fixture=false, không thêm registry. Root run_repair hiện sẽ từ chối
  native execution fixture này; không bật flag hoặc nới guard để chạy cho qua.
- M2-W9-3 phụ trách admission SWE-bench, không phải nhiệm vụ của fixture này.
- M3 dùng fixture để phát triển runner/contract. Full fake-runner integration,
  resume và real model qualification phải nghiệm thu riêng; W9-6 không sửa M3.
- Không có gold/reference patch trong context hoặc few-shot của fixture.
