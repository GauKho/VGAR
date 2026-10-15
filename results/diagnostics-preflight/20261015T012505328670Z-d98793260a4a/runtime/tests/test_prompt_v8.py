import re

from test_bootstrap import api


def test_v8_context_body_example_retains_prefix_and_original_python_indentation(tmp_path):
    text = api('prompt').template_path('m2-w78-v8').read_text(encoding='utf-8')
    bodies = re.findall(r'BEGIN BODY EXAMPLE\n(.*?)END BODY EXAMPLE', text, re.S)
    assert len(bodies) == 1
    original = b'MARKER = 0\n\n\n\n\ndef neutral(value):\n    kept = value\n    return kept\n'
    (tmp_path / 'neutral.py').write_bytes(original)
    raw = '--- a/neutral.py\n+++ b/neutral.py\n@@ -6,3 +6,3 @@\n' + bodies[0]
    module = api('patch')
    patch = module.parse_unified_diff(raw, module.PatchPolicy(('neutral.py',), ()))
    predicted, _ = module._bind(patch, tmp_path)
    assert predicted['neutral.py'] == b'MARKER = 0\n\n\n\n\ndef neutral(value):\n    kept = value\n    return kept + kept\n'
    assert (tmp_path / 'neutral.py').read_bytes() == original
