"""V11 replacement contract over real M1 node ranges: methods start at their indentation column.

M3 preflight (25/10) found every paired W9 bundle rejected because method snippets start at column 4.
The fix widens such a snippet to whole lines with the source's own leading whitespace; nothing else changes.
"""
from types import SimpleNamespace

import pytest

from vgar.repair.context_presentation import present_context
from vgar.repair.evidence import digest

SOURCE = 'class Box:\n    def size(self):\n        return 1\n\n    def name(self):\n        return "box"\n'


def handoff(tmp_path, snippet, start_line, start_col, end_line, end_col, *, allowed=('box.py',)):
    (tmp_path / 'box.py').write_bytes(SOURCE.encode())
    item = SimpleNamespace(node_id='n1', path='box.py', symbol='Box.size', snippet=snippet,
                           range=SimpleNamespace(start_line=start_line, start_col=start_col,
                                                 end_line=end_line, end_col=end_col),
                           relevance_score=1.0, confidence=1.0)
    task = SimpleNamespace(source_repo=tmp_path, allowed_source_paths=allowed, protected_paths=('tests',))
    return SimpleNamespace(assert_unchanged=lambda: None, task=task, context_text='m1 context',
                           context=SimpleNamespace(graph_version='g', items=[item]),
                           manifest={'files': {'box.py': digest(SOURCE.encode())}})


def test_indented_method_is_widened_to_whole_lines(tmp_path):
    method = 'def size(self):\n        return 1'
    text, meta = present_context(handoff(tmp_path, method, 2, 4, 3, 16), patch_contract=True)
    [item] = meta['source_items']
    assert item['start_column'] == 0 and item['leading_whitespace_added'] == 4
    assert item['patch_old_start'] == 2 and item['patch_old_count'] == 2
    assert '--- BEGIN SOURCE ---\n    def size(self):\n        return 1\n--- END SOURCE ---' in text
    assert 'Source_start: 2:0' in text


def test_code_before_snippet_on_first_line_is_still_rejected(tmp_path):
    with pytest.raises(ValueError, match='complete source lines'):
        present_context(handoff(tmp_path, 'size(self):\n        return 1', 2, 8, 3, 16), patch_contract=True)


def test_whole_line_snippet_is_unchanged(tmp_path):
    whole = '    def size(self):\n        return 1\n'
    text, meta = present_context(handoff(tmp_path, whole, 2, 0, 4, 0), patch_contract=True)
    [item] = meta['source_items']
    assert item['leading_whitespace_added'] == 0
    assert '--- BEGIN SOURCE ---\n' + whole + '--- END SOURCE ---' in text


def test_read_only_snippet_keeps_original_text(tmp_path):
    method = 'def size(self):\n        return 1'
    text, meta = present_context(handoff(tmp_path, method, 2, 4, 3, 16, allowed=()), patch_contract=True)
    [item] = meta['source_items']
    assert item['edit_permission'] == 'read-only' and item['start_column'] == 4
    assert '--- BEGIN SOURCE ---\n' + method + '\n--- END SOURCE ---' in text
