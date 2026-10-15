"""Read-only delivery validation; writes only the dedicated validation receipt."""
import sys

sys.dont_write_bytecode = True
import importlib.metadata as md
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from vgar_m2_w78.b_experiment import runtime_fingerprint
from vgar_m2_w78.campaign import assess_record

receipt = root / 'results/delivery-validation/delivery_check.json'
checks = {}


def require(name, condition):
    checks[name] = bool(condition)
    if not condition:
        raise RuntimeError(name)


try:
    targets = [
        'docs/01_BAN_GIAO_M2_W7_W8_CHO_M1_M3.md',
        'docs/02_BAO_CAO_TOAN_BO_M2_W7_W8.md',
        'docs/03_LENH_POWERSHELL_A_B_C_V11_R002.md',
        'requirement.txt', 'test_abc_v11_r002.ps1',
    ]
    require('five_deliverables_exist', all((root / p).is_file() for p in targets))
    script = (root / targets[-1]).read_text(encoding='utf-8').rstrip()
    doc3 = (root / targets[2]).read_text(encoding='utf-8')
    mirror = doc3.split('## 6. Toàn bộ script liền mạch', 1)[1]
    mirror = mirror.split('```powershell\n', 1)[1].split('\n```', 1)[0]
    require('doc3_exact_script_mirror', mirror.rstrip() == script)
    lines = {int(n) for n in re.findall(r'^### Dòng (\d+)$', doc3, re.M)}
    require('doc3_each_nonempty_line_explained', lines == {
        i for i, text in enumerate(script.splitlines(), 1) if text.strip()
    })
    pins = dict(re.findall(r'^([a-zA-Z0-9_-]+)==([^\s]+)$',
                           (root / 'requirement.txt').read_text(encoding='utf-8'), re.M))
    require('core_dependency_pins_match', len(pins) == 7 and all(
        md.version(name) == version for name, version in pins.items()))
    prior = root / 'results/b_repair/2026-10-15-evidence-driven-b'
    old = json.loads((prior / 'frozen_inputs.json').read_text(encoding='utf-8'))
    revision = json.loads((prior / 'revisions/r002.json').read_text(encoding='utf-8'))
    expected = {PureWindowsPath(p).relative_to(PureWindowsPath(old['runtime_root'])).as_posix(): h
                for p, h in revision['files'].items()}
    current = {Path(p).relative_to(root).as_posix(): h for p, h in runtime_fingerprint(root).items()}
    require('qualified_core_r002_unchanged', current == expected)
    final = root / 'results/final_acceptance/2026-10-15-v11-r002'
    records = [next((final / c).glob('*/run_record.json')) for c in 'ABC']
    require('saved_real_abc_core_acceptance', all(
        assess_record(p)['status'] == 'PASS' for p in records))
    suite = json.loads((root / 'results/delivery-validation/final-full-suite/'
                       '20261015T090448960637Z-611d502a76ad/run_record.json').read_text(encoding='utf-8'))
    require('fresh_core234_pass', suite['status'] == 'PASS' and
            suite['stages']['pytest']['exit_code'] == 0 and
            '234 passed' in suite['stages']['pytest']['stdout'])
    junit = ET.parse(root / 'results/delivery-validation/green-review-all.xml').getroot()
    suites = [junit] if junit.tag == 'testsuite' else list(junit)
    require('runner8_pass', sum(int(s.attrib['tests']) for s in suites) == 8 and
            all(int(s.attrib.get('failures', 0)) == int(s.attrib.get('errors', 0)) == 0 for s in suites))
    lint = subprocess.run([str(root / '.venv/Scripts/python.exe'), '-m', 'ruff', 'check',
                           '--select', 'E9,F', 'src', 'scripts', 'tests',
                           '.superpowers/sdd/2026-10-15-m2-delivery-package'],
                          cwd=root, capture_output=True, text=True, timeout=60)
    require('ruff_pass', lint.returncode == 0)
    ps = subprocess.run(['powershell', '-NoProfile', '-Command',
                         "$t=$null; $e=$null; [System.Management.Automation.Language.Parser]::ParseFile(" 
                         "(Join-Path $PWD 'test_abc_v11_r002.ps1'),[ref]$t,[ref]$e) | Out-Null; "
                         "if($e.Count){$e;exit 1}; 'PowerShell syntax PASS'"],
                        cwd=root, capture_output=True, text=True, timeout=60)
    require('powershell_syntax_pass', ps.returncode == 0)
    inventory = (root / targets[1]).read_text(encoding='utf-8')
    listed_files = set(re.findall(r'^\| `([^`]+)` \| FILE \|', inventory, re.M))
    listed_dirs = set(re.findall(r'^\| `([^`]+)/` \| DIR \|', inventory, re.M))
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    actual_dirs = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir()}
    require('inventory_all_files_exact', listed_files == actual_files)
    require('inventory_all_directories_exact', listed_dirs == actual_dirs)
    result = dict(status='PASS', checks=checks, files=len(actual_files),
                  directories=len(actual_dirs), ruff_stdout=lint.stdout,
                  powershell_stdout=ps.stdout, new_model_generations=0)
except Exception as exc:
    result = dict(status='ERROR', checks=checks, reason=repr(exc), new_model_generations=0)
    raise
finally:
    result['checked_utc'] = datetime.now(timezone.utc).isoformat()
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
