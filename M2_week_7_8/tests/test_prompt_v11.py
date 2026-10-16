"""V11 removes literal wrapper markers observed in attempt-01 raw output."""
from pathlib import Path

from test_bootstrap import api


def test_v11_has_no_copyable_format_delimiters_and_keeps_valid_neutral_diff(tmp_path):
    root = Path(__file__).resolve().parents[1]
    template = (root/'prompts/repair_v11.txt').read_text(encoding='utf-8')
    assert 'BEGIN FORMAT DIFF' not in template and 'END FORMAT DIFF' not in template
    start = template.index('--- a/neutral_left.py')
    end_line = "+    return '<' + kept + '>'\n"
    end = template.index(end_line, start)+len(end_line)
    raw = template[start:end]
    parsed = api('patch').parse_unified_diff(raw, api('patch').PatchPolicy(
        ('neutral_left.py','neutral_right.py'), ('tests',)))
    assert len(parsed.files) == 2
