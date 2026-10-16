import re

from test_bootstrap import api


def test_v9_neutral_replacement_uses_existing_strict_parser_and_git_apply(tmp_path):
    text = api('prompt').template_path('m2-w78-v9').read_text(encoding='utf-8')
    examples = re.findall(r'BEGIN FORMAT DIFF\n(.*?)END FORMAT DIFF', text, re.S)
    assert len(examples) == 1
    original = b'MARKER = 0\n\ndef twice(x):\n    return x\n'
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'neutral.py').write_bytes(original)
    module = api('patch')
    patch = module.parse_unified_diff(examples[0], module.PatchPolicy(('neutral.py',), ('tests',)))
    assert all(row[0] in '+-' for row in patch.files['neutral.py'][0]['body'])
    with api('workspace').create_workspace(source, tmp_path / 'private') as lease:
        result = module.apply_patch(lease, patch, api('executor').NativeExecutor(lease))
        assert result.status == 'PASS'
        assert (lease.path / 'neutral.py').read_bytes() == original.replace(b'return x', b'return x + x')
    assert (source / 'neutral.py').read_bytes() == original
