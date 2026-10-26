"""Build/validate the portable W9 consumer fixture. Offline; never run repairs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from vgar.contracts.handoff import byte_digest  # noqa: E402
from vgar.graph.builder import PythonGraphBuilder  # noqa: E402
from vgar.graph.handoff import create_context_handoff, write_context_handoff  # noqa: E402
from vgar.graph.sqlite_service import SQLiteGraphService  # noqa: E402
from vgar.graph.sqlite_store import SQLiteGraphStore  # noqa: E402
from vgar.repair.config import load_task  # noqa: E402
from vgar.repair.context_adapter import load_handoff  # noqa: E402

CANONICAL = ROOT/'tests/fixtures/w9_bundle'
ORIGINAL = ROOT/'tests/fixtures/w7_w8_handoff/single_file_login/repo'
TASK_ID = 'w9-single-file-login'
REPO_KEY = 'fixture/w9/single-file-login'
REVISION = 'w9-fixture-v1'
ISSUE = 'auth.py login accepts whitespace-only names; trim the name before checking whether it is empty.'
FAILING = 'tests/test_auth.py::test_login_rejects_whitespace'
COUNTER_LABEL = 'fixture-only:characters'
SOURCE_FILES = ('auth.py', 'pytest.ini', 'tests/test_auth.py')
BUNDLE_FILES = ('context.json', 'context_manifest.json', 'test_links.json', 'repair-context.txt')
HASHED_FILES = ('task.json', *(f'repo/{p}' for p in SOURCE_FILES), *(f'bundle/{p}' for p in BUNDLE_FILES))

README = r'''# M1-W9-6 — Fixture bàn giao cho M2/M3

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
'''


def write_json(path: Path, value) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def counter_for(manifest: Path | None):
    if manifest is None:
        return len, COUNTER_LABEL, {'counter_mode': 'fixture-only', 'counter_label': COUNTER_LABEL,
            'counting_policy': 'len(text):unicode-characters:sum-item-counts', 'tokenizer_identity': None}
    from vgar.graph.token_counter import LocalTokenizerCounter
    counter = LocalTokenizerCounter(manifest)
    data = json.loads(Path(manifest).read_text(encoding='utf-8'))
    identity = {k: data[k] for k in ('model_id', 'revision', 'counting_policy', 'weights_downloaded')}
    identity['files'] = sorted(data['files'], key=lambda row: row['name'])
    return counter, counter.counter_label, {'counter_mode': 'local-tokenizer',
        'counter_label': counter.counter_label, 'counting_policy': data['counting_policy'],
        'tokenizer_identity': identity}


def hash_file(root: Path, relative: str) -> str:
    path = root/relative
    if any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError('Fixture links are not allowed')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Fixture path escapes root')
    return byte_digest(path.read_bytes())


def load_fixture(root: Path, *, tokenizer_manifest: Path | None = None):
    root = Path(root).resolve()
    profile = json.loads((root/'fixture_profile.json').read_text(encoding='utf-8'))
    if set(profile['files']) != set(HASHED_FILES):
        raise ValueError('Unexpected fixture hash inventory')
    for relative, expected in profile['files'].items():
        if hash_file(root, relative) != expected:
            raise ValueError('Fixture file hash mismatch: '+relative)
    raw = json.loads((root/'task.json').read_text(encoding='utf-8'))
    if raw['source_repo'] != 'repo' or raw['bundle_directory'] != 'bundle' or raw.get('trusted_fixture') is not False:
        raise ValueError('Fixture paths or admission flag changed')
    task = load_task(root/'task.json')
    identity = {'task_id': task.task_id, 'repo_key': task.repo_key, 'revision': task.revision,
        'graph_version': task.graph_version}
    if identity != profile['identity'] or (task.task_id, task.repo_key, task.revision) != (TASK_ID, REPO_KEY, REVISION):
        raise ValueError('Fixture task identity mismatch')
    mode = profile['counter_mode']
    if (mode == 'fixture-only') != (tokenizer_manifest is None):
        raise ValueError('Select the matching fixture/tokenizer counter profile explicitly')
    count, label, observed = counter_for(tokenizer_manifest)
    if any(profile.get(k) != value for k, value in observed.items()):
        raise ValueError('Fixture counter identity mismatch')
    received = load_handoff(task, count, label)
    if received.metadata['source_digest'] != profile['source_digest']:
        raise ValueError('Fixture source identity mismatch')
    return received


def build_fixture(output_root: Path, *, tokenizer_manifest: Path | None = None) -> dict:
    output = Path(output_root).resolve()
    for protected in (CANONICAL.resolve(), ORIGINAL.resolve()):
        if protected == CANONICAL.resolve() and output == protected and not output.exists():
            continue  # Initial canonical generation only; subsequent calls cannot overwrite it.
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('Output overlaps a protected fixture')
    if output.exists():
        raise FileExistsError(output)
    count, label, counter_profile = counter_for(tokenizer_manifest)
    if CANONICAL.exists():
        load_fixture(CANONICAL)
        source = CANONICAL/'repo'
    else:
        source = ORIGINAL
    source_bytes = {name: (source/name).read_bytes() for name in SOURCE_FILES}
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in source_bytes.items():
        target = output/'repo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output/'.gitattributes').write_bytes(b'* -text\n')
    document = PythonGraphBuilder(repo_key=REPO_KEY, repository_revision=REVISION).build(output/'repo')
    anchors = [node['id'] for node in document['nodes'] if node['type'] == 'Function' and node['path'] == 'auth.py']
    if len(anchors) != 1:
        raise ValueError('Expected one login source anchor')
    with tempfile.TemporaryDirectory(prefix='vgar-w9-fixture-') as scratch:
        store = SQLiteGraphStore(Path(scratch)/'graph.db')
        store.ingest(document)
        service = SQLiteGraphService(store, repository_root=output/'repo', count_tokens=count, counter_label=label)
        response = service.get_related_context(anchors, 8000, graph_version=document['graph_version'],
            task_id=TASK_ID, issue_text=ISSUE, failing_tests=[FAILING])
        bundle = create_context_handoff(document, response, output/'repo', count_tokens=count,
            counter_label=label, changed_paths=['auth.py'], failing_tests=[FAILING], selected_tests=['tests'])
        write_context_handoff(bundle, output/'bundle')
    task = {'task_id': TASK_ID, 'issue_text': ISSUE, 'source_repo': 'repo', 'repo_key': REPO_KEY,
        'revision': REVISION, 'graph_version': document['graph_version'], 'bundle_directory': 'bundle',
        'failing_selectors': [FAILING], 'fallback_scope': ['tests'], 'allowed_source_paths': ['auth.py'],
        'protected_paths': ['tests', 'pytest.ini'], 'trusted_fixture': False}
    write_json(output/'task.json', task)
    profile = {**counter_profile, 'recipe': 'scripts/build_w9_bundle_fixture.py',
        'resolver': 'static', 'snippet_budget': 8000,
        'origin': 'tests/fixtures/w7_w8_handoff/single_file_login/repo (initial byte copy)',
        'identity': {k: task[k] for k in ('task_id', 'repo_key', 'revision', 'graph_version')},
        'source_digest': bundle['manifest']['source_digest'],
        'files': {name: hash_file(output, name) for name in HASHED_FILES}}
    write_json(output/'fixture_profile.json', profile)
    (output/'README.md').write_bytes(README.encode('utf-8'))
    handoff = load_fixture(output, tokenizer_manifest=tokenizer_manifest)
    if {name: (source/name).read_bytes() for name in SOURCE_FILES} != source_bytes:
        raise ValueError('Original source changed while building fixture')
    return summary(handoff, output, 'build')


def summary(handoff, root: Path, mode: str) -> dict:
    return {'status': 'PASS', 'mode': mode, 'fixture_root': str(root),
        'task_id': handoff.task.task_id, 'graph_version': handoff.task.graph_version,
        'source_digest': handoff.metadata['source_digest'], 'counter_label': handoff.metadata['counter_label'],
        'context_items': len(handoff.context.items), 'snippet_count': handoff.context.total_token_count,
        'collection_verified': False, 'coverage_verified': False, 'repair_execution': 'NOT_RUN'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--output-root', type=Path, help='Create a NEW fixture directory; never overwrite')
    action.add_argument('--validate-root', type=Path, help='Read and validate an existing fixture only')
    parser.add_argument('--tokenizer-manifest', type=Path, help='Optional verified local assets, no downloads')
    args = parser.parse_args()
    try:
        if args.output_root is not None:
            report = build_fixture(args.output_root, tokenizer_manifest=args.tokenizer_manifest)
        else:
            directory = args.validate_root.resolve()
            report = summary(load_fixture(directory, tokenizer_manifest=args.tokenizer_manifest), directory, 'validate')
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return 0
    except Exception:  # noqa: BLE001 -- CLI preserves diagnostics; no fallback or output repair
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
