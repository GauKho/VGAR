"""V11 removes literal wrapper markers observed in attempt-01 raw output."""
import hashlib

import pytest

from w78_support import REPO
from vgar.repair import patch as m_patch
from vgar.repair import prompt as m_prompt


def test_v11_has_no_copyable_format_delimiters_and_keeps_valid_neutral_diff(tmp_path):
    template = (REPO/'src/vgar/agents/prompts/repair_v11.txt').read_text(encoding='utf-8')
    assert 'BEGIN FORMAT DIFF' not in template and 'END FORMAT DIFF' not in template
    start = template.index('--- a/neutral_left.py')
    end_line = "+    return '<' + kept + '>'\n"
    end = template.index(end_line, start)+len(end_line)
    raw = template[start:end]
    parsed = m_patch.parse_unified_diff(raw, m_patch.PatchPolicy(
        ('neutral_left.py','neutral_right.py'), ('tests',)))
    assert len(parsed.files) == 2


def test_only_v11_is_registered():
    assert hashlib.sha256(m_prompt.template_path("m2-w78-v11").read_bytes()).hexdigest().startswith("ba6d1478")
    for version in ("m2-w78-v1", "m2-w78-v10", "m2-w78-v12"):
        with pytest.raises(ValueError, match="Unregistered or missing prompt version"):
            m_prompt.template_path(version)


def test_v11_template_lives_with_the_agent_prompts():
    assert m_prompt.template_path("m2-w78-v11") == REPO / "src/vgar/agents/prompts/repair_v11.txt"
    assert not (REPO / "src/vgar/repair/prompts").exists()
