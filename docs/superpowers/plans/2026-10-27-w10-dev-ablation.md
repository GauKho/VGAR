# W10 Dev Ablation A0–A2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chạy A0–A2 trên dev theo hai nấc (10 → 30 task), và sinh bảng kèm phễu chẩn đoán từ record đã lưu.

**Architecture:** Giữ nguyên engine M2. Có 3 điểm mở rộng:
- Bước chuẩn hóa diff chạy trước parser strict, bật bằng `patch_mode` trong variant.
- Adapter test runner chỉ đổi lệnh **trong container**. Phía host vẫn là argv pytest cùng report `nodeids.json`/`junit.xml`, nên `test_runner.py`, `verification.py` và admission không đổi.
- Population lấy từ một manifest W10 khóa. `task_env`, export bundle và harness được tổng quát hóa từ 5 ID pilot sang "manifest đã duyệt + `limit`".

Aggregate chỉ đọc record, report harness và gold patch sau khi run đã xong.

**Tech Stack:** Python 3.11 (host, WSL), pydantic, pytest, Docker (`unix://`), swebench 4.1.0 (chỉ cho harness), pyarrow.

**Spec:** `docs/superpowers/specs/2026-10-27-w10-dev-ablation-design.md`

## Global Constraints

- Dataset `princeton-nlp/SWE-bench_Verified` rev `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, parquet `sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`.
- Model `Qwen/Qwen3-4B-Instruct-2507` rev `cdbee75f17c01a7cc42f958dc650907174af0554`, `input_cap` 6000, `output_cap` 1536. Không đổi model trong W10.
- Gold patch, `test_patch` và FAIL_TO_PASS không được vào prompt, bundle, test tái hiện, manifest W10, hay bất kỳ input nào của generator. Gold chỉ được đọc trong `aggregate.py` và harness.
- Fixture, golden và config W9 hiện có phải giữ nguyên hash: `policy_hash` của A0/A1/A2 W9, `experiment_id` `55ee3300aca339e8`, profile `vgar-task-env-v1`.
- `patch_mode` mặc định là `strict`. W10 dùng `normalized` cho cả 3 arm.
- Population W10 loại 5 task pilot, dùng `min_source_files=1`, khóa trước khi chạy nấc 1.
- Runner, `task_env` và harness chạy trong WSL2, Docker `unix:///var/run/docker.sock`, harness `--max_workers 1`.
- Chạy model là việc **người dùng tự chạy** và dán output. Agent không tự chạy hay kill run GPU.
- **Người dùng tự commit.** Các bước "Commit" dưới đây chỉ là đề xuất file và lệnh, agent không chạy `git commit`.
- `native_runner.py` chạy bằng Python của testbed, nên phải viết được cho **Python ≥ 3.5** và chỉ dùng stdlib. Lý do: swebench ghi Django 1.4–2.2 dùng Python 3.5, và dev có 1 task Django 1.11. Nghĩa là không dùng f-string, không dùng annotation, không dùng `subprocess.run(capture_output=..., text=...)`.
- Lệnh test và loại runner **không gõ tay**. Chúng lấy từ bảng `configs/m1/swebench_410_test_cmds.json`, sinh từ `MAP_REPO_VERSION_TO_SPECS` của swebench 4.1.0 và khóa theo `(repo, version)`. Repo hoặc version không có trong bảng thì báo lỗi, không mặc định là pytest.
- `graph.json` dùng cho aggregate được ràng buộc bằng `{path, sha256}` trong experiment config. Khi load phải kiểm `repo_key` và `repository_revision` của document khớp với task.
- Luôn báo cả `strict_apply` lẫn `normalized_apply`. Mẫu số luôn là N = toàn bộ population, kể cả task bị loại hoặc chưa chạy.

## Review Focus

1. **Parser bỏ sót test sau khi đã có patch.** Vì mỗi arm sinh patch khác nhau, lỗi này có thể tạo false reject lệch về một arm. Parser phải đúng với cả 4 họ log: Django 1.11, Django 3.0–4.0, Django ≥ 4.1 (in `test_x (pkg.mod.Class.test_x)`), và test có docstring in kết quả ở dòng sau. Test thuộc Task 5.
2. **Model viết các hunk sai thứ tự**, hunk sau nằm trước hunk trước trong file. Phải ra `CONTEXT_NOT_FOUND`, không được âm thầm khớp lùi. Test thuộc Task 2.
3. **File base dùng CRLF hoặc không có newline cuối.** Diff chuẩn hóa phải đi qua `_bind` và `git apply --check` mà không đổi byte ngoài vùng sửa. Test thuộc Task 2.
4. **Runner gốc ghi file vào `/testbed`** (cache sympy, `.pyc`). Snapshot sau khi chạy phải bằng snapshot trước, nếu không executor báo ERROR hạ tầng. Test tích hợp thuộc Task 5.
5. **Cặp task × variant chỉ có attempt `INTERRUPTED` hoặc chưa có attempt nào.** Cặp đó vẫn nằm trong N, với trạng thái `NOT_RUN`, không bị bỏ. Test thuộc Task 11.

## PR theo CODEOWNERS

| PR | Task | Người duyệt |
|---|---|---|
| `m3/w10-repair-engine` | 1–5 | `@tmthien220205-ai` (`src/vgar/repair/`) |
| `m3/w10-population-harness` | 6–9 | `@17dangkhoi17` (harness, task_env) |
| `m3/w10-evaluation` | 10–11 | M3 |
| `m3/w10-docs` | 15 | cả nhóm |

Trước Task 12, D12 phải có trong `main`. Kiểm bằng `git branch --contains 3393266d` và xem có `main` không. Nếu chưa có thì merge PR của `m3/w09-close` trước.

Phần impact (§5.3: M1-W10-1/2, M3-W10-3/4) **không nằm trong plan này**. Làm plan riêng sau khi cổng W10 đạt.

---

### Task 1: `patch_mode` trong VariantPolicy, giữ nguyên hash W9

**Files:**
- Modify: `src/vgar/repair/policy.py`
- Create: `configs/m2/variants/w10/A0.json`, `A1.json`, `A2.json`
- Test: `tests/m2/w910/test_policy.py` (thêm test)

**Interfaces:**
- Produces: `VariantPolicy.patch_mode: Literal['strict', 'normalized'] = 'strict'`. `model_dump()` và `policy_hash()` **bỏ key `patch_mode` khi giá trị là `'strict'`**, để hash và snapshot đã lưu của W9 không đổi.

- [ ] **Step 1: Chụp hash hiện tại.** Chạy `python -c "from pathlib import Path;from vgar.repair.policy import load_variant,policy_hash;[print(v,policy_hash(load_variant(Path(f'configs/m2/variants/{v}.json')))) for v in ('A0','A1','A2')]"` (với `PYTHONPATH=src`). Dán 3 giá trị vào test ở Step 2.

- [ ] **Step 2: Viết test (sẽ fail)**

```python
W9_HASHES = {'A0': 'sha256:<từ Step 1>', 'A1': 'sha256:<...>', 'A2': 'sha256:<...>'}

def test_w9_variant_hashes_unchanged():
    for v, expected in W9_HASHES.items():
        policy = load_variant(ROOT / f'configs/m2/variants/{v}.json')
        assert policy.patch_mode == 'strict'
        assert 'patch_mode' not in policy.model_dump(mode='json')
        assert policy_hash(policy) == expected

def test_w10_variants_are_normalized_and_hash_differs():
    for v in ('A0', 'A1', 'A2'):
        policy = load_variant(ROOT / f'configs/m2/variants/w10/{v}.json')
        assert policy.patch_mode == 'normalized'
        assert policy.model_dump(mode='json')['patch_mode'] == 'normalized'
        assert policy_hash(policy) != W9_HASHES[v]

def test_unknown_patch_mode_rejected():
    with pytest.raises(ValidationError):
        VariantPolicy(variant_id='A0', required_checks=('tests',), patch_mode='fuzzy')
```

- [ ] **Step 3:** Chạy `pytest tests/m2/w910/test_policy.py -q`. Mong đợi: FAIL (thiếu file w10, thiếu field).

- [ ] **Step 4: Implement.** Thêm field `patch_mode` và một `@model_serializer(mode='wrap')` bỏ `patch_mode` khi giá trị là `'strict'`. Các file `w10/A*.json` là bản sao của file W9 cùng tên, thêm `"patch_mode": "normalized"`.

- [ ] **Step 5:** Chạy `pytest tests/m2/w910 tests/m3 -q`. Mong đợi: PASS hết, vì không test W9 nào được đổi hash.

- [ ] **Step 6: Commit (người dùng chạy):** `git add src/vgar/repair/policy.py configs/m2/variants/w10 tests/m2/w910/test_policy.py && git commit -m "feat(repair): add patch_mode to variant policy, hash-stable for strict"`

---

### Task 2: Module chuẩn hóa diff

**Files:**
- Create: `src/vgar/repair/patch_normalize.py`
- Create fixtures: `tests/fixtures/m2/w10_normalize/<case>/raw.diff` cùng các file base mà diff đụng tới, giữ đúng đường dẫn trong repo (`<case>/src/<repo path>`)
- Test: `tests/m2/w910/test_patch_normalize.py`

**Interfaces:**
- Consumes: `PatchPolicy`, `_name`, `parse_unified_diff`, `_bind` từ `vgar.repair.patch`.
- Produces:
```python
class NormalizationError(ValueError):
    code: Literal['NO_OP', 'CONTEXT_NOT_FOUND', 'CONTEXT_AMBIGUOUS']

@dataclass(frozen=True)
class NormalizedPatch:
    diff: str                 # unified diff chuẩn, parse được bằng parser strict
    hunks_total: int
    hunks_noop_dropped: int
    hunks_relocated: int      # vị trí khớp khác số dòng trong header, hoặc header không đọc được

def normalize_unified_diff(raw: str, root: Path, policy: PatchPolicy) -> NormalizedPatch
```

Luật chuẩn hóa là 6 luật ở spec §5.4, không thêm luật nào. Các điểm builder không tự suy ra được:
- Header file (fence `diff`, `diff --git`, `---`/`+++`, path a/b, allowed/protected) kiểm bằng `_name` và đúng điều kiện của `_parse_unified_diff` **trước khi** đọc file từ `root`.
- Một dòng `--- ` chỉ là header file khi dòng ngay sau nó bắt đầu bằng `+++ `. Nếu không, đó là dòng `-` có nội dung bắt đầu bằng `-- `.
- So khớp theo nội dung dòng đã bỏ `\r\n`. Tìm từ sau vị trí kết thúc của hunk trước trong cùng file.
- Sinh lại diff bằng `difflib.unified_diff(..., n=3, lineterm='')` trên các dòng không có EOL, ghi `\ No newline at end of file` khi dòng cuối của file cũ hoặc mới nằm trong hunk mà không có newline. Kết quả cuối phải qua được `parse_unified_diff(diff, policy)`.

- [ ] **Step 1: Tạo fixture từ 6 run pilot.** Raw output nằm ở `~/vgar/results/m3/55ee3300aca339e8/engine/<task>__<variant>/attempt-*/<run>/raw_model_output.txt`, file base lấy từ `~/w9/repositories/<task>`. Có 6 case: `matplotlib_A0`, `matplotlib_A1`, `xarray_A0`, `xarray_A1`, `pylint_A0`, `pylint_A1`. Chỉ chép những file mà diff đụng tới.

- [ ] **Step 2: Viết test (sẽ fail)**

```python
EXPECTED = {'matplotlib_A0': 'OK', 'pylint_A1': 'OK',
            'matplotlib_A1': 'NO_OP', 'xarray_A1': 'NO_OP',
            'xarray_A0': 'CONTEXT_NOT_FOUND', 'pylint_A0': 'CONTEXT_NOT_FOUND'}

@pytest.mark.parametrize('case,expected', EXPECTED.items())
def test_pilot_diffs(case, expected): ...
    # OK -> NormalizedPatch; parse_unified_diff(result.diff, policy) và _bind(parsed, root) không raise
    # còn lại -> NormalizationError với .code == expected

def test_wrong_header_counts_are_ignored(tmp_path): ...       # @@ -1,99 +1,99 @@ trên hunk 3 dòng -> OK, hunks_relocated == 1
def test_blank_line_is_empty_context(tmp_path): ...           # dòng rỗng trong thân hunk khớp dòng rỗng của file
def test_ambiguous_context(tmp_path): ...                     # khối cũ xuất hiện 2 lần -> CONTEXT_AMBIGUOUS
def test_hunks_out_of_order(tmp_path): ...                    # Review Focus 2 -> CONTEXT_NOT_FOUND
def test_crlf_and_missing_final_newline(tmp_path): ...        # Review Focus 3: bytes sau _bind chỉ khác ở dòng sửa
def test_removed_line_starting_with_double_dash(tmp_path): ... # '--- x' không có '+++' theo sau là dòng '-'
def test_protected_path_still_rejected(tmp_path): ...         # ValueError (không phải NormalizationError), không đọc file
def test_partial_noop_hunk_dropped(tmp_path): ...             # 2 hunk, 1 no-op -> OK, hunks_noop_dropped == 1
```

- [ ] **Step 3:** Chạy `pytest tests/m2/w910/test_patch_normalize.py -q`. Mong đợi: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4:** Implement `normalize_unified_diff` trong `src/vgar/repair/patch_normalize.py`.

- [ ] **Step 5:** Chạy lại test. Mong đợi: PASS hết. Nếu một case pilot ra khác bảng `EXPECTED` thì **dừng lại và báo người dùng**. Bảng này đến từ spec §1, không được sửa cho khớp code.

- [ ] **Step 6: Commit (người dùng chạy):** `git add src/vgar/repair/patch_normalize.py tests/fixtures/m2/w10_normalize tests/m2/w910/test_patch_normalize.py && git commit -m "feat(repair): diff normalization with exact-unique context relocation"`

---

### Task 3: Gắn chuẩn hóa vào session

**Files:**
- Modify: `src/vgar/repair/session.py` (`apply_candidate`)
- Test: `tests/m2/w910/test_patch_mode_session.py`

**Interfaces:**
- Consumes: Task 1 (`variant.patch_mode`), Task 2 (`normalize_unified_diff`, `NormalizationError`).
- Produces: `run_record.stages.parse_patch.patch_normalization = {mode, strict_parse_ok, strict_apply_ok, hunks_total, hunks_noop_dropped, hunks_relocated, normalized_diff_sha256}` khi `mode == 'normalized'`, **kể cả khi FAIL**. Outcome là `('FAIL', 'NO_OP' | 'CONTEXT_NOT_FOUND' | 'CONTEXT_AMBIGUOUS')`. Thêm artifact `normalized.diff`.

Hành vi:
- `mode` lấy từ `session.experiment.variant_policy.patch_mode`. Không có experiment thì là `strict`, và đường strict giữ nguyên từng dòng.
- Khi `normalized`:
  - `strict_parse_ok`: `parse_unified_diff(raw, pp)` không raise.
  - `strict_apply_ok`: `strict_parse_ok` và `_bind(parsed, lease.path)` không raise. Chỉ để ghi lại, không ảnh hưởng kết cục.
  - Sau đó chạy `normalize_unified_diff(raw, lease.path, pp)`, rồi `parse_unified_diff(normalized.diff, pp)`, rồi `apply_patch` như cũ.
- Gặp `NormalizationError`: ghi stage `parse_patch` với `status='FAIL'`, `complete=True`, `patch_normalization` và `error={code, message}`, rồi `raise StopRun('FAIL', e.code)`.

- [ ] **Step 1: Viết test (sẽ fail).** Dùng fixture native `single_file_login` (xem `tests/m3/conftest.py::fixture_config`) với `FakeGenerator`, chạy qua `run_repair(..., experiment={'variant_policy': <w10 A0 dict>, 'arm': 'bm25'})`.

```python
def test_normalized_fixes_bad_header_and_records_strict_probe(...):
    # reference patch với header số dòng sai
    record = run(...).record
    pn = record['stages']['parse_patch']['patch_normalization']
    assert pn['mode'] == 'normalized' and pn['strict_parse_ok'] is False
    assert record['stages']['apply']['status'] == 'PASS'

def test_noop_candidate_fails_with_no_op_code(...):
    assert (record['status'], record['reason']) == ('FAIL', 'NO_OP')
    assert record['stages']['parse_patch']['patch_normalization']['hunks_noop_dropped'] >= 1

def test_strict_mode_unchanged(...):  # variant W9 A0: header sai -> ('FAIL', 'PATCH_PARSE_ERROR'), không có key patch_normalization
```

- [ ] **Step 2:** Chạy `pytest tests/m2/w910/test_patch_mode_session.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Implement trong `apply_candidate`.
- [ ] **Step 4:** Chạy `pytest tests/m2 tests/m3 -q`. Mong đợi: PASS hết. Golden W7-8 không đổi.
- [ ] **Step 5: Commit (người dùng chạy):** `git add src/vgar/repair/session.py tests/m2/w910/test_patch_mode_session.py && git commit -m "feat(repair): normalized patch mode in apply step with strict probe evidence"`

---

### Task 4: Mã failure có cấu trúc

**Files:**
- Create: `src/vgar/repair/failure.py`
- Modify: `src/vgar/repair/session.py` (`finish`), `src/vgar/evaluation/repair/launch.py` (`classify_record`), `src/vgar/evaluation/repair/runner.py` (`_attempt`)
- Test: `tests/m2/w910/test_failure.py`, cập nhật `tests/m3/test_launch.py` và `tests/m3/test_runner.py` nếu đang assert `stage is None`

**Interfaces:**
- Produces:
```python
def failure_of(record: dict) -> dict | None
# None khi record['status'] == 'PASS'; ngược lại trả về {stage, code, cause, evidence_ref}:
# stage = record['error_detail']['stage'] nếu có; nếu không thì stage đầu tiên theo thứ tự session.STAGES có status FAIL/ERROR;
#         nếu không có thì 'finalization' khi có finalization_errors, còn lại là 'verification'
# code  = record['reason'] or 'INTERNAL_ERROR'
# cause = message ngắn (≤ 500 ký tự): error_detail.message, hoặc stages[stage].error.message / .reason
# evidence_ref = f'run_record.json#stages/{stage}'
```
- `session.finish` ghi `run.record['failure'] = failure_of({**run.record, 'status': status, 'reason': reason})` ngay trước `run.finish`.
- `classify_record` lấy `stage` từ `(record.get('failure') or failure_of(record) or {}).get('stage')`. Cách này cũng áp được cho record pilot cũ chưa có `failure`.
- Attempt record của runner có thêm `failure`. Lỗi phía runner (`plan`, `admission`, `launch`, `record`) dùng `{stage, code: reason, cause: dòng cuối của detail, evidence_ref: None}`.

- [ ] **Step 1: Viết test (sẽ fail).** Gồm:
  - `failure_of` trên các record tối thiểu, mỗi loại một case: FAIL `PATCH_PARSE_ERROR` có `error_detail`, FAIL `PATCH_APPLY_FAILED` không có `error_detail` (stage `apply`), ERROR `VERIFICATION_INCOMPLETE` ở baseline, `NO_OP`, PASS → `None`.
  - Test runner: một plan `TASK_EXCLUDED` cho ra attempt có `failure.stage == 'plan'`.
- [ ] **Step 2:** Chạy `pytest tests/m2/w910/test_failure.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Implement theo phần Interfaces.
- [ ] **Step 4:** Chạy `pytest tests/m2 tests/m3 -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit (người dùng chạy):** `git add src/vgar/repair/failure.py src/vgar/repair/session.py src/vgar/evaluation/repair/launch.py src/vgar/evaluation/repair/runner.py tests && git commit -m "feat(repair): structured failure {stage, code, cause, evidence_ref} on every terminal record"`

---

### Task 5: Adapter test runner gốc (Django, sympy)

**Files:**
- Create: `src/vgar/repair/native_runner.py` (script chạy trong container, Python ≥ 3.6, chỉ dùng stdlib)
- Modify: `src/vgar/repair/docker_executor.py` (`map_command`, danh sách file chép vào `control`)
- Create fixtures: `tests/fixtures/m2/native_runner/django_runtests.log`, `django41_runtests.log`, `sympy_bin_test.log`
- Test: `tests/m2/w910/test_native_runner.py` (unit), `tests/m2/w910/test_native_runner_docker.py` (tích hợp, `pytest.mark.skipif(os.environ.get('VGAR_DOCKER_TESTS') != '1')`)

**Interfaces:**
- Consumes: profile có `test_runner` (Task 7). Thiếu field thì dùng `'pytest'`.
- Produces (trong `native_runner.py`):
```python
RUNNERS = ('django_runtests', 'sympy_bin_test')
def django_label(selector: str) -> str        # 'tests/a/tests.py::C::test_x' -> 'a.tests.C.test_x'; 'tests/a/tests.py' -> 'a.tests'
def sympy_file(selector: str) -> str          # 'sympy/a/tests/test_r.py::test_x' -> 'sympy/a/tests/test_r.py'
def parse_django(log: str) -> tuple[dict, list]   # ({node_id: status}, collection_errors)
def parse_sympy(log: str) -> tuple[dict, list]
def main(argv) -> int
# argv: --runner R --report PATH --junit PATH [--collect-only] SELECTOR...
```
- Node id phải theo dạng pytest để `expand_required` dùng được: Django là `tests/<app path>.py::<Class>::<test>`, sympy là `<file>::<test>`. Status dùng đúng tập của `pytest_plugin`: `PASS/FAIL/ERROR/SKIP/XFAIL/XPASS`.
- Report JSON có **đúng các key** của `pytest_plugin.STATE`: `node_ids, outcomes, durations_ms, collection_errors, complete, exit_code`. `junit.xml` là một `<testsuite>` hợp lệ.
- Exit code: chế độ collect trả 0 khi có node id và không có lỗi collection, ngược lại trả 2. Chế độ chạy trả 0 khi mọi test PASS, 1 khi có FAIL/ERROR, 2 khi không có test nào hoặc có lỗi collection.
- Với sympy, chạy theo file và chỉ giữ trong report những test được selector chọn. Selector chỉ nêu file thì giữ mọi test của file.
- Lệnh chạy **không gõ cứng trong `native_runner.py`**. Nó nhận `--command-json '{"env": {...}, "argv": [...]}'` lấy từ `profile['native_command']` (Task 7, sinh từ bảng `(repo, version)`), rồi chạy `[sys.executable, *argv, *labels_or_files]` với env cộng thêm. Ví dụ với Django 3.0, argv là `["tests/runtests.py", "--verbosity", "2", "--settings=test_sqlite", "--parallel", "1"]`.
- `DockerExecutor.map_command`: giữ nguyên toàn bộ phần kiểm argv và selector pytest. Riêng khi `profile.get('test_runner', 'pytest') != 'pytest'`, argv được map sang `[profile['python'], '/vgar/vgar_native_runner.py', '--runner', R, '--command-json', json.dumps(profile['native_command'], sort_keys=True), '--report', '/vgar/nodeids.json', '--junit', '/vgar/junit.xml', *tail]`. Thêm `native_runner.py` vào danh sách chép thành `vgar_native_runner.py`.

- [ ] **Step 1: Lưu log fixture.** Chạy lại 2 lệnh spike (spec §4) và lưu stdout vào `django_runtests.log` và `sympy_bin_test.log`. Lấy thêm **log thật của image Django 1.11 và một image Django ≥ 4.1** (chọn từ manifest W10), lưu vào `django111_runtests.log` và `django41_runtests.log`. Mỗi log có 1 test pass, 1 test fail và 1 test có docstring.

- [ ] **Step 2: Viết test unit (sẽ fail)**

```python
def test_django_label():
    assert django_label('tests/vgar_repro/tests.py::Repro::test_x') == 'vgar_repro.tests.Repro.test_x'
    assert django_label('tests/vgar_repro/tests.py') == 'vgar_repro.tests'
    with pytest.raises(ValueError): django_label('django/db/models.py')

def test_parse_django_spike_log():
    outcomes, errors = parse_django(read('django_runtests.log'))
    assert outcomes == {'tests/vgar_repro/tests.py::Repro::test_fail': 'FAIL',
                        'tests/vgar_repro/tests.py::Repro::test_pass': 'PASS'}
    assert errors == []

@pytest.mark.parametrize('log', ['django_runtests.log', 'django111_runtests.log', 'django41_runtests.log'])
def test_parse_django_all_families(log):  # Review Focus 1
    outcomes, _ = parse_django(read(log))
    assert outcomes['tests/vgar_repro/tests.py::Repro::test_fail'] == 'FAIL'
    assert outcomes['tests/vgar_repro/tests.py::Repro::test_pass'] == 'PASS'
    assert outcomes['tests/vgar_repro/tests.py::Repro::test_doc'] == 'PASS'

def test_source_is_python35_compatible():
    src = (ROOT / 'src/vgar/repair/native_runner.py').read_text(encoding='utf-8')
    ast.parse(src, feature_version=(3, 5))
    assert 'capture_output' not in src and 'text=True' not in src and "f'" not in src and 'f"' not in src
    # vermin --target=3.5 khi có cài vermin; nếu không có thì pytest.skip cho riêng phần này

def test_parse_django_import_error_is_collection_error(): ...  # 'ImportError: Failed to import test module: vgar_repro.tests'

def test_parse_sympy_spike_log():
    outcomes, errors = parse_sympy(read('sympy_bin_test.log'))
    assert outcomes == {'sympy/vgar_repro/tests/test_repro.py::test_fail': 'FAIL',
                        'sympy/vgar_repro/tests/test_repro.py::test_pass': 'PASS'}

def test_report_keys_match_pytest_plugin(tmp_path): ...  # main() với subprocess giả lập -> set(report) == set(pytest_plugin.STATE) | {'exit_code'}

def test_docker_map_command_native(tmp_path): ...
    # profile test_runner='django_runtests': argv[1] == '/vgar/vgar_native_runner.py', selector ngoài scope vẫn bị từ chối
def test_docker_map_command_pytest_unchanged(tmp_path): ...  # profile v1 -> argv giống hệt hiện tại
```

- [ ] **Step 3:** Chạy `pytest tests/m2/w910/test_native_runner.py -q`. Mong đợi: FAIL.
- [ ] **Step 4:** Implement `native_runner.py` và phần sửa `docker_executor.py`.
- [ ] **Step 5:** Chạy `pytest tests/m2 tests/m3 -q`. Mong đợi: PASS.
- [ ] **Step 6: Test tích hợp.** Dựng `DockerExecutor` trên image `django-11138`, `sympy-20590` và **image Django 1.11 của dev (Python 3.5, đây là cổng thật cho ràng buộc Python 3.5)** với overlay repro gồm 1 test pass và 1 test fail, chạy collect và run. Assert outcome như Step 2, và assert `target_result.snapshot_after == snapshot_before` (Review Focus 4). Chạy trong WSL bằng `VGAR_DOCKER_TESTS=1 .venv/bin/python -m pytest tests/m2/w910/test_native_runner_docker.py -q`. Mong đợi: 2 passed. Nếu snapshot lệch thì ghi file nào lệch, rồi chặn file đó bằng env trong lệnh (ví dụ `PYTHONDONTWRITEBYTECODE=1`), không nới kiểm tra snapshot.
- [ ] **Step 7: Commit (người dùng chạy):** `git add src/vgar/repair/native_runner.py src/vgar/repair/docker_executor.py tests/fixtures/m2/native_runner tests/m2/w910/test_native_runner*.py && git commit -m "feat(repair): native Django/sympy test runner adapter behind pytest report contract"`

---

### Task 6: Bảng lệnh test, manifest W10 khóa và checkout

**Files:**
- Create: `scripts/build_swebench_test_cmds.py` (chạy bằng venv có swebench 4.1.0), `configs/m1/swebench_410_test_cmds.json` (sinh ra, commit), `src/vgar/evaluation/harness/test_cmds.py`
- Modify: `src/vgar/evaluation/retrieval/pilot_manifest.py`, `scripts/prepare_w9_pilot_inputs.py`
- Create (sinh ra, commit): `configs/m1/w10_dev_manifest.json`

**Bảng lệnh test:**
- Định dạng: `{"swebench_version": "4.1.0", "repos": {repo: {version: {"runner": R, "env": {...}, "argv": [...], "source": "<test_cmd gốc>"}}}}`.
- Lấy env và argv bằng `shlex.split` trên `test_cmd`. Các token `KEY=VALUE` ở đầu được đưa vào `env`. Bỏ `./` ở đầu argv.
- Quy tắc chọn runner:
  - `test_cmd` bắt đầu bằng `pytest` → `pytest`.
  - Sphinx `tox --current-env -epy39 -v --` → `pytest`, ghi `"equivalence": "tox --current-env runs pytest"`.
  - Chứa `runtests.py` → `django_runtests`.
  - Chứa `bin/test` → `sympy_bin_test`.
  - Còn lại → `unsupported`.
- `test_cmds.py`:
  - `load_test_cmds(path=ROOT/'configs/m1/swebench_410_test_cmds.json') -> dict`
  - `lookup(table, repo, version) -> dict`: báo `ValueError` khi không có `(repo, version)` hoặc runner là `unsupported`.
- **Kiểm sớm:** khi sinh manifest W10, mọi task phải `lookup` được. Thiếu thì dừng, không ghi manifest.
- Test: `tests/test_w9_pilot_bundles.py` hoặc file test hiện có của `pilot_manifest` (thêm test)

**Interfaces:**
- Produces:
```python
def project_retrieval_task(row, *, with_version=False) -> dict   # with_version=True thêm 'version' (không phải thông tin gold)
def make_manifest(rows, *, parquet_hash, selection_policy='repo_round_robin_then_instance_id_v1:multi-file') -> dict
def validate_manifest(manifest, *, expected_hash=None, expected_ids=PILOT_IDS) -> None   # expected_ids=None: bỏ kiểm population
W10_SELECTION = 'repo_round_robin_then_instance_id_v1:min1-excluding-w9-pilot'
# with_version = (selection_policy == W10_SELECTION), nên manifest pilot giữ nguyên hash
```
- Script: `prepare_w9_pilot_inputs.py --population {w9-pilot,w10-dev} [--count 50] [--limit N] [--prepare-sources]`. Với `w10-dev`: bỏ các dòng có `instance_id in PILOT_IDS`, gọi `select_tasks(rows, 50, split='dev', min_source_files=1)`, `make_manifest(..., selection_policy=W10_SELECTION)`, rồi `locked_json(configs/m1/w10_dev_manifest.json)`. `--limit` chỉ checkout N task đầu.

- [ ] **Step 1: Viết test (sẽ fail).**
  - `validate_manifest(w9_manifest)` vẫn PASS với tham số mặc định.
  - Một manifest W10 tổng hợp: `validate_manifest(m, expected_ids=None)` PASS, `validate_manifest(m)` raise "differs from approved five tasks".
  - Mọi task W10 chỉ có các key `instance_id, repo, base_commit, problem_statement, query_hash, split, version` (không có gold). Manifest pilot không có `version` và giữ nguyên hash `sha256:98984466…`.
  - Bảng lệnh test: `lookup(t, 'django/django', '1.11')['runner'] == 'django_runtests'`. Sphinx ra `pytest` và có `equivalence`. `lookup(t, 'x/y', '1.0')` raise. Cả 4 runner được phân loại đúng trên `test_cmd` mẫu.
  - Kiểm sớm: một task có version không có trong bảng thì việc sinh manifest raise và không ghi file.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests -q -k "manifest or pilot"`. Mong đợi: PASS.
- [ ] **Step 5: Sinh manifest.** Chạy `python scripts/prepare_w9_pilot_inputs.py --population w10-dev --dataset-cache data/downloads/c104f840cc67f8b6eec6f759ebc8b2693d585d4a --tokenizer-cache <như W9>`. Mong đợi: in ra `INPUTS READY sha256:...`, file có 50 task, không chứa task pilot nào. Chạy lại lần hai phải ra cùng hash (khóa).
- [ ] **Step 6: Commit (người dùng chạy):** `git add src/vgar/evaluation/retrieval/pilot_manifest.py scripts/prepare_w9_pilot_inputs.py configs/m1/w10_dev_manifest.json tests && git commit -m "feat(m1): locked W10 dev manifest (50 candidates, min_source_files=1, pilot excluded)"`

---

### Task 7: Profile môi trường v2 có `test_runner`

**Files:**
- Modify: `src/vgar/evaluation/harness/task_env.py`, `src/vgar/evaluation/harness/collection_probe.py`
- Create: `scripts/pin_task_images.py`, `configs/m1/w10_task_env_profile.json` (`UNQUALIFIED`, `images: {}`)
- Test: `tests/test_task_env.py` (thêm test)

**Interfaces:**
- Consumes: `native_runner.py` (Task 5), `validate_manifest(..., expected_ids=None)` (Task 6).
- Produces:
```python
SCHEMA_V2 = 'vgar-task-env-v2'; NATIVE_PROTOCOL = 'vgar-native-sentinel-v1'
def runner_for(repo: str, version: str, table: dict) -> dict  # = test_cmds.lookup; không có mặc định
def validate_profile(profile, *, expected_task=None) -> dict   # nhận v1 (không có test_runner) và v2
def prepare(manifest_path, runtime_path, bundle_root, output_root, *, execute=False, prepare_images=False,
            approved_manifest=ROOT/'configs/m1/w9_pilot_manifest.json', limit=None) -> dict
```
- Profile v2 có thêm field `test_runner` và `native_command` (`{env, argv}` lấy từ bảng; với pytest thì là `null`). Với runner native:
  - `scope == ['@native-sentinel']`, `probe_protocol == NATIVE_PROTOCOL`, `runtime['pytest']` được phép là `None`.
  - `COLLECTED` khi và chỉ khi chạy sentinel (1 test pass do probe tự viết vào `/testbed`, xóa sau khi chạy) cho ra `exit_code == 0` và `node_ids == [<sentinel id>]`.
  - Sentinel Django là `tests/vgar_sentinel/tests.py::Sentinel::test_ok`, sympy là `sympy/vgar_sentinel/tests/test_sentinel.py::test_ok`.
  - `source_before` phải bằng `source_after` như v1.
- `main()` có thêm `--approved-manifest PATH` và `--limit N`, truyền thẳng vào `prepare`.
- Runtime config: tập key của `images` phải là **tiền tố** của danh sách ID trong manifest đã duyệt (theo thứ tự). `PILOT_IDS` chỉ còn là mặc định của tham số.
- `pin_task_images.py --manifest M --runtime R --limit N`: với N task đầu, chạy `docker pull swebench/sweb.eval.x86_64.<id with __ → _1776_>:latest`, ghi `reference = repo@<RepoDigest>` và `image_id: null`. Khi đủ N task thì đặt `qualification_state = 'PINNED'`.

- [ ] **Step 1: Viết test (sẽ fail).**
  - Profile v1 pilot đã lưu (fixture trong `tests/m3/conftest.py`) vẫn validate, và có `test_runner` ngầm định là pytest.
  - Profile v2 Django `COLLECTED` với sentinel thì hợp lệ. Profile v2 Django mà `node_ids` khác sentinel thì bị từ chối.
  - `load_runtime` với `images` là tiền tố thì PASS, không phải tiền tố thì raise.
  - `runner_for('sympy/sympy', '1.9', t)['runner'] == 'sympy_bin_test'`. Repo hoặc version không có trong bảng thì raise.
- [ ] **Step 2:** Chạy `pytest tests/test_task_env.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests -q`. Mong đợi: PASS. `tests/m3` vẫn dùng profile v1.
- [ ] **Step 5: Commit (người dùng chạy):** `git add src/vgar/evaluation/harness/task_env.py src/vgar/evaluation/harness/collection_probe.py scripts/pin_task_images.py configs/m1/w10_task_env_profile.json tests/test_task_env.py && git commit -m "feat(m1): task env profile v2 with native test runner qualification"`

---

### Task 8: Export bundle theo manifest đã duyệt

**Files:**
- Modify: `scripts/export_w9_pilot_bundles.py`
- Test: `tests/test_w9_pilot_bundles.py`

**Interfaces:**
- Thêm tham số `--approved-manifest PATH` (mặc định là manifest pilot) và `--limit N`. `expected_bundles = 2 * số task được xử lý`.
- Layout đầu ra không đổi: `<run>/<task>/graph.json` và `<run>/<task>/{graph,bm25}/...`. Khi copy sang data root W10 (`~/w10/bundles/repair/<task>/`) phải giữ `graph.json` ở cấp task, vì aggregate (Task 11) đọc file này cho F5.

- [ ] **Step 1: Viết test (sẽ fail).** Gọi `main` với manifest tổng hợp 1 task và `--approved-manifest` trỏ tới chính file đó. Kiểm `expected_bundles == 2`. Gọi lại không có `--approved-manifest` thì vẫn từ chối manifest khác pilot.
- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests/test_w9_pilot_bundles.py -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit (người dùng chạy):** `git add scripts/export_w9_pilot_bundles.py tests/test_w9_pilot_bundles.py && git commit -m "feat(m1): bundle export for any approved manifest"`

---

### Task 9: Harness chấm candidate

**Files:**
- Modify: `src/vgar/evaluation/harness/gold_inputs.py`, `src/vgar/evaluation/harness/official.py`
- Create: `scripts/grade_repair_candidates.py`, `configs/m1/w10_harness_profile.json`
- Test: `tests/test_official_harness.py` (thêm test)

**Interfaces:**
- Produces:
```python
# gold_inputs.py
def select_rows(rows, manifest, instance_ids, *, approved_manifest: Path) -> list[dict]   # select_gold_rows gọi lại hàm này với GOLD_IDS
# official.py
def collect_candidates(exp_dir: Path) -> list[dict]
#  attempt TERMINAL mới nhất của từng cặp có engine_run_dir, run_record.stages.apply.status == 'PASS' và có applied.diff
#  -> {experiment_id, task_id, variant_id, arm, run_id, model_patch, patch_sha256}
def grade_candidates(manifest_path, harness_profile, exp_dirs, output_root, *, approved_manifest, execute,
                     dataset_parquet=None) -> dict
#  mỗi candidate: một predictions.jsonl riêng, model_name_or_path = f'vgar-w10-{variant_id}', một lần gọi run_evaluation
#  -> ghi <run>/grades.json: {'grades': [{experiment_id, task_id, variant_id, run_id, patch_sha256,
#                                          harness_status: 'RESOLVED'|'UNRESOLVED'|'ERROR', report_ref}]}
```
- `preflight(profile, directory, instance_ids)` và `read_report(raw_dir, instance_id, patch, model_label)` có thêm tham số. Đường gold W9 vẫn gọi với `GOLD_IDS` và `MODEL_LABEL` như cũ.
- Diff được chấm là `applied.diff`, tức bản đã chuẩn hóa và đã apply, không phải raw output.
- Output phải nằm dưới `results/` (giữ kiểm tra hiện có).

- [ ] **Step 1: Viết test (sẽ fail).**
  - `collect_candidates` trên một experiment dir tổng hợp gồm 3 cặp: chỉ cặp có apply PASS được lấy, và `model_patch == applied.diff`.
  - `grade_candidates(..., execute=False)` ghi đúng 1 predictions file cho mỗi candidate với label đúng, và không gọi subprocess.
  - Chạy gold W9 với `execute=False` vẫn ra cùng argv như trước.
- [ ] **Step 2:** Chạy `pytest tests/test_official_harness.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests -q`. Mong đợi: PASS.
- [ ] **Step 5: Kiểm thu M1-W10-4 (trong WSL):** `python scripts/grade_repair_candidates.py --experiment-dir results/m3/55ee3300aca339e8 --manifest configs/m1/w9_pilot_manifest.json --approved-manifest configs/m1/w9_pilot_manifest.json --profile <harness profile pilot> --dataset-parquet <parquet> --execute`. Mong đợi: `grades.json` có đúng các candidate pilot đã apply PASS (có thể là 0), không có `ERROR`.
- [ ] **Step 6: Commit (người dùng chạy):** `git add src/vgar/evaluation/harness scripts/grade_repair_candidates.py configs/m1/w10_harness_profile.json tests/test_official_harness.py && git commit -m "feat(m1): grade repair candidates with the official harness"`

---

### Task 10: Tập con task cho experiment và kiểm arm tương đương

**Files:**
- Modify: `src/vgar/evaluation/repair/manifest.py` (`load_experiment`), `scripts/run_repair_experiment.py`
- Create: `src/vgar/evaluation/repair/fairness.py`
- Test: `tests/m2/w910/test_arm_fairness.py`, `tests/m3/test_manifest.py` (thêm test)

**Interfaces:**
- `source.task_ids` (không bắt buộc): danh sách không trùng, là tập con của manifest. `Experiment.task_ids` theo đúng thứ tự này. Identity chỉ thêm `task_ids` và chỉ giới hạn `task_inputs` **khi có key này**, để `experiment_id` pilot giữ nguyên `55ee3300aca339e8`.
- `source.bundle_profile` (không bắt buộc): `{path, sha256}`. `load_experiment` kiểm sha.
- `source.bundles[task].graph` (không bắt buộc): `{path, sha256}`. `load_experiment` kiểm sha. Hàm `load_graph(exp, task_id, data_root) -> dict | None` kiểm thêm `document['repo_key'] == row['repo']` và `document['repository_revision'] == row['base_commit']`, lệch thì raise. Không có key thì trả `None`.
- Produces:
```python
def fairness_identity(exp: Experiment) -> dict
#  {model_id, revision, tokenizer_manifest_sha, template_sha, policy (RepairPolicy.model_dump()),
#   bundle_profile_sha (hoặc None), variant_common: policy variant đã bỏ {variant_id, arm, required_checks}}
def check_arm_fairness(experiments: Sequence[Experiment]) -> None
#  ValueError('Arm fairness violation: <field>') nếu variant_common khác nhau giữa các variant,
#  hoặc fairness_identity khác nhau giữa các experiment
```
- `run_repair_experiment.py run` gọi `check_arm_fairness([exp])` **trước** `run_experiment`. Lệch thì thoát mã 2 và không tạo thư mục experiment.

- [ ] **Step 1: Viết test (sẽ fail)**

```python
def test_only_arm_and_checks_may_differ(...):      # W10 A0/A1/A2 -> không raise
def test_patch_mode_mismatch_rejected(...):        # A0 normalized, A1 strict -> 'patch_mode' có trong message
def test_cross_experiment_input_cap_mismatch(...): # hai config khác input_cap -> raise
def test_refused_run_writes_nothing(tmp_path, ...): # main(['run', ...]) -> exit 2, không có output_root/<id>
def test_task_ids_subset_and_pilot_id_stable(...): # pilot config -> '55ee3300aca339e8'; task_ids ngoài manifest -> ValueError
```

- [ ] **Step 2:** Chạy test. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests/m2 tests/m3 -q`. Mong đợi: PASS.
- [ ] **Step 5: Commit (người dùng chạy):** `git add src/vgar/evaluation/repair scripts/run_repair_experiment.py tests && git commit -m "feat(m3): experiment task subsets and arm fairness gate"`

---

### Task 11: Aggregate và phễu

**Files:**
- Create: `src/vgar/evaluation/repair/aggregate.py`
- Modify: `scripts/run_repair_experiment.py` (lệnh `aggregate`)
- Test: `tests/m3/test_aggregate.py`

**Interfaces:**
- Consumes: `failure_of` (Task 4), `check_arm_fairness` (Task 10), `grades.json` (Task 9), `changed_source_files`, `diff_to_nodes`.
- CLI: `run_repair_experiment.py aggregate --config C1 [--config C2 ...] --data-root D [--grades G ...] --parquet P --out DIR`. `--config` dùng `action='append'`. Các lệnh cũ vẫn chỉ nhận đúng một config. Ghi ra `DIR/aggregate.json` và `DIR/aggregate.md`.
- Produces:
```python
def pair_rows(exp: Experiment, exp_dir: Path, data_root: Path, grades: dict, gold: dict) -> list[dict]
def summarize(rows: list[dict]) -> dict
def render_markdown(summary: dict) -> str
def aggregate(configs: list[Path], data_root: Path, output_root: Path, grade_files: list[Path], parquet: Path) -> tuple[dict, str]
```
- Mỗi row ứng với một task × variant của **mọi** experiment, lấy attempt mới nhất. Không có attempt `TERMINAL` thì `status = 'NOT_RUN'` (Review Focus 5). Trường của row:
  - `task_id, variant_id, arm, experiment_id, status, failure{stage, code}` (dùng `failure_of` cho record cũ)
  - `F1..F8`
  - `harness_status ∈ {RESOLVED, UNRESOLVED, ERROR, NOT_GRADED}`
  - `multi_file`
  - `mypy_available` (`stages.baseline.static.mypy.report.execution_status != 'UNAVAILABLE'`)
  - `cost{input_tokens, output_tokens, generation_ms, model_load_ms, wall_ms, generation_count}` và `cost_missing{field: reason}`
- Định nghĩa F lấy đúng bảng ở spec §5.9:
  - F2 là `parse_patch.patch_normalization.strict_apply_ok`. Record strict thì F2 = F3.
  - F4 và F5 tính từ `applied.diff` so với gold patch (đọc từ parquet).
  - F5 dùng `diff_to_nodes` với graph lấy từ `load_graph` (Task 10, đã kiểm hash và danh tính) và `PatchPolicy(allowed_paths=<mọi path trong graph>, protected_paths=())`. So ở mức node `Function`/`Method`. Lỗi hoặc thiếu graph thì ghi `'unavailable'`.
  - F6 là `stages.verification.policy_checks.tests.status == 'PASS'`.
  - false reject: harness `RESOLVED` mà `status != 'PASS'`. false accept: `status == 'PASS'` mà harness `UNRESOLVED`.
- `summarize`: với mỗi variant gồm N (= số task của population, kể cả loại hoặc chưa chạy), số đếm và tỷ lệ F1..F8 trên N, F5 `unavailable` đếm riêng, phân bố `failure.code`, trung bình cost (bỏ `null`, ghi kèm số mẫu), và các subgroup `multi_file` / `mypy_available`. Không có p-value.
- Xác định từng byte: `json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)`, không có timestamp, không có đường dẫn tuyệt đối.

- [ ] **Step 1: Viết test (sẽ fail).** Tạo experiment tổng hợp bằng `tests/m3/m3_support.py` gồm 3 task × 3 variant, với run record JSON viết tay:

```python
def test_denominator_includes_excluded_and_not_run(...):  # 1 task TASK_EXCLUDED, 1 cặp chỉ INTERRUPTED -> N == 3 cho mọi variant
def test_funnel_counts(...):                               # strict fail + normalized ok -> F2=0, F3=1; F8 cần F7 và RESOLVED
def test_false_accept_and_reject(...):
def test_legacy_record_without_failure_gets_stage(...):    # record kiểu pilot: stage != None
def test_f5_unavailable_when_graph_missing(...):
def test_byte_identical_rerun(tmp_path, ...):              # aggregate 2 lần -> cùng bytes cho json và md
def test_cross_experiment_fairness_enforced(...):          # 2 config lệch -> ValueError
```

- [ ] **Step 2:** Chạy `pytest tests/m3/test_aggregate.py -q`. Mong đợi: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Chạy `pytest tests -q`. Mong đợi: PASS.
- [ ] **Step 5: Kiểm thu trên pilot (WSL).** Chạy `aggregate --config configs/m3/w9_pilot.json --data-root ~/w9 --parquet <P> --out results/m3/agg-pilot` hai lần, rồi `cmp` hai `aggregate.json`. Mong đợi: giống hệt, 15 row, không row nào có `failure.stage` là `null` (kiểm thu §5.5).
- [ ] **Step 6: Commit (người dùng chạy):** `git add src/vgar/evaluation/repair/aggregate.py scripts/run_repair_experiment.py tests/m3/test_aggregate.py && git commit -m "feat(m3): deterministic A0-A2 aggregate with diagnostic funnel"`

---

### Task 12: Chuẩn bị nấc 1 (vận hành, không TDD)

Mọi lệnh chạy trong WSL, data root là `~/w10`. Kết quả mỗi bước được ghi vào `docs/status/` (theo mẫu W9).

- [ ] **Step 1:** Chạy `pin_task_images.py --manifest configs/m1/w10_dev_manifest.json --runtime configs/m1/w10_task_env_profile.json --limit 15`. Mong đợi: 15 reference `@sha256:`, state `PINNED`. Có thể chạy nền.
- [ ] **Step 2:** Chạy `prepare_w9_pilot_inputs.py --population w10-dev --prepare-sources --limit 15 --sources-root ~/w10/repositories`.
- [ ] **Step 3:** Chạy `prepare_task_env.py --manifest configs/m1/w10_dev_manifest.json --approved-manifest configs/m1/w10_dev_manifest.json --runtime configs/m1/w10_task_env_profile.json --limit 15 --prepare-images --execute`. Mong đợi: `COMPLETE`. **Population nấc 1** = tiền tố ngắn nhất có đủ 10 task `COLLECTED`. Chưa đủ thì tăng `--limit` (pin thêm image ở Step 1) cho đến khi đủ, hoặc đến hết 50 ứng viên.
- [ ] **Step 4:** Export bundle cho các task `COLLECTED` trong tiền tố, với `--approved-manifest configs/m1/w10_dev_manifest.json --profile configs/m1/w9_bundle_profile_repair.json`, rồi copy sang `~/w10/bundles/repair/<task>/`.
- [ ] **Step 5: Test tái hiện.** Với mỗi task `COLLECTED`, viết `configs/m3/w10_dev/tasks/<id>.json` và `<id>.repro.py` theo D4 và `configs/m3/w9_pilot/tasks/README.md`.
  - Admission yêu cầu dấu `vgar_w9_repro_` trong đường dẫn overlay, và file không được rỗng.
  - Django: overlay `tests/vgar_w9_repro_<x>/__init__.py` (một dòng comment) và `tests/vgar_w9_repro_<x>/tests.py`, `protected_paths` có `tests`. **Chưa chạy được** khi vấn đề symlink `docs/*.png` chưa có quyết định (xem ledger W10).
  - Sympy: overlay `sympy/vgar_w9_repro_<x>/test_repro.py` (không cần `__init__.py`; `bin/test` chỉ chạy `test_*.py` nằm trong package), `protected_paths` có `sympy/vgar_w9_repro_<x>`.
  - Kiểm FAIL trên base theo runbook W9 Bước 5. Với Django/sympy, thay lệnh pytest bằng lệnh runner gốc ở Task 5.
  - Task không viết được test đáng tin thì ghi lý do vào `configs/m3/w10_dev/tasks/EXCLUDED.md` **trước khi chạy**. Task đó vẫn nằm trong mẫu số (runner ghi `TASK_INPUT_MISSING`).
- [ ] **Step 6:** Viết `configs/m3/w10_dev_stage1.json` theo dạng `w9_pilot.json`:
  - `task_ids` = population nấc 1.
  - Variants là `../m2/variants/w10/A{0,1,2}.json` với arm `bm25`, `graph`, `graph`.
  - `bundle_profile` trỏ tới `w9_bundle_profile_repair.json`.
- [ ] **Step 7:** Chạy `run_repair_experiment.py preflight --config configs/m3/w10_dev_stage1.json --data-root ~/w10`. Mong đợi: mọi cặp `FITS`, `TASK_EXCLUDED` hoặc `TASK_INPUT_MISSING` đã ghi lý do. Có `OVER_CAP` thì ghi task đó là loại kèm lý do, không cắt tay.
- [ ] **Step 8: Commit (người dùng chạy):** cấu hình nấc 1, task inputs và status doc.

### Task 13: Chạy nấc 1 và kiểm §7 (người dùng chạy GPU)

- [ ] **Step 1 (người dùng):** Chạy `run_repair_experiment.py run --config configs/m3/w10_dev_stage1.json --data-root ~/w10`, khoảng 30 run, qua đêm. Dán bảng `status` khi xong.
- [ ] **Step 2:** Chạy `grade_repair_candidates.py --experiment-dir results/m3/<id> --manifest configs/m1/w10_dev_manifest.json --approved-manifest configs/m1/w10_dev_manifest.json --profile configs/m1/w10_harness_profile.json --execute`.
- [ ] **Step 3:** Chạy `aggregate` hai lần và `cmp` hai kết quả.
- [ ] **Step 4: Kiểm §7.** Cần cả 4 điều:
  1. Mỗi task có đủ 3 record `TERMINAL`.
  2. Không có `ERROR` hạ tầng.
  3. `aggregate` ra kết quả giống hệt nhau.
  4. `grades.json` không có `ERROR`.

  Không đạt thì sửa hạ tầng rồi `run --rerun TASK:VARIANT --reason "<lỗi hạ tầng>"`. Không bao giờ chạy lại vì kết quả của model.

### Task 14: Nấc 2 (lên tổng 30 task)

- [ ] **Step 1:** Lặp lại Task 12 Step 1–5, tăng `--limit` cho đến khi tiền tố có đủ 30 task `COLLECTED`, hoặc hết 50 ứng viên thì báo đúng N có được.
- [ ] **Step 2:** Viết `configs/m3/w10_dev_stage2.json`, giống nấc 1 nhưng `task_ids` = 20 task mới. Chạy `preflight` (fairness được kiểm trong `run`).
- [ ] **Step 3 (người dùng):** `run`, khoảng 60 run.
- [ ] **Step 4:** Chấm harness cho experiment nấc 2. Chạy `aggregate --config ...stage1.json --config ...stage2.json`, kèm cả hai file grades. Mong đợi: fairness giữa hai experiment PASS, 30 × 3 row, chạy hai lần ra giống hệt.

### Task 15: Ghi quyết định và Methodology

**Files:** `docs/m3_w10_decisions.md` (mới), `docs/paper/` (mục 5.2, 5.4 và bản nháp Experimental Design)

- [ ] **Step 1:** Viết D13 (chuẩn hóa diff, `patch_mode`, hash ổn định cho strict), D14 (population hai nấc, `min_source_files=1`, loại pilot, quy tắc tiền tố), D15 (oracle là test tái hiện, harness chấm `applied.diff`, F8 = được chấp nhận và resolved), và D16 (adapter runner gốc, kết quả spike ngày 27/10).
- [ ] **Step 2:** Viết Methodology v1 theo engine thật, như spec §5.10. Viết trong lúc chờ run.
- [ ] **Step 3: Commit (người dùng chạy).**
