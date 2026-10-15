"""V6 guards the observed V5 error: 3 original lines declared as count 2."""
import re

from test_bootstrap import api


def test_v6_examples_bind_two_and_three_line_hunks_with_unchanged_assignment(tmp_path):
    text = api('prompt').template_path('m2-w78-v6').read_text(encoding='utf-8')
    examples = re.findall(r'BEGIN FORMAT DIFF\n(.*?)END FORMAT DIFF', text, re.S)
    assert len(examples) == 1
    originals = dict(origin_a=b'MARKER = 0\n\ndef magnitude(n):\n    return n\n',
        origin_b=b'MARKER = 0\n\n\n\n\ndef doubled(n):\n    x = n\n    return x\n')
    for name, data in originals.items():
        (tmp_path / (name + '.py')).write_bytes(data)
    module = api('patch')
    parsed = module.parse_unified_diff(examples[0], module.PatchPolicy(('origin_a.py','origin_b.py'), ()))
    predicted, _ = module._bind(parsed, tmp_path)
    assert (parsed.files['origin_a.py'][0]['old'], parsed.files['origin_a.py'][0]['oc']) == (3, 2)
    assert (parsed.files['origin_b.py'][0]['old'], parsed.files['origin_b.py'][0]['oc']) == (6, 3)
    assert (' ', '    x = n', False) in [tuple(row) for row in parsed.files['origin_b.py'][0]['body']]
    assert predicted['origin_b.py'] == b'MARKER = 0\n\n\n\n\ndef doubled(n):\n    x = n\n    return x + x\n'
    assert all((tmp_path / (n + '.py')).read_bytes() == data for n,data in originals.items())
