"""M3-W12-3: docs/security_checklist.md covers S1–S16, states its limits, and every referenced test exists."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / 'docs/security_checklist.md'
REF = re.compile(r'`(tests/[\w/]+\.py)::(\w+)`')


def test_checklist_covers_s1_to_s16_and_states_limits():
    text = CHECKLIST.read_text(encoding='utf-8')
    assert [f'S{i}' for i in range(1, 17) if f'| S{i} |' not in text] == []
    assert '## Giới hạn' in text and 'pytest vẫn chạy code của target' in text
    assert 'an toàn tuyệt đối' not in text.replace('không phải an toàn tuyệt đối', '')


def test_every_referenced_test_exists():
    refs = REF.findall(CHECKLIST.read_text(encoding='utf-8'))
    assert len(refs) >= 16
    missing = [f'{path}::{name}' for path, name in refs
               if not (ROOT / path).is_file()
               or not re.search(rf'^\s*(async\s+)?def {name}\b', (ROOT / path).read_text(encoding='utf-8'), re.M)]
    assert missing == []
