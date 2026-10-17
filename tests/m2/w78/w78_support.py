"""Shared helpers for the M2 W7-W8 tests (ported from the original M2 package conftest)."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / 'examples/m2'
GRAPHS = {
    'single_file_login': 'sha256:e1fe94d21f10f112cd3a5e2a39f88e1fb26a760ee8ea3eaa6d3bac608d1ec371',
    'multi_file_invoice': 'sha256:1bbff47bc1ee5098b1f3d8f37dc5952faa9127224763e651c66630d838adb93e',
    'missing_links': 'sha256:ac135fa480d1f999d33e943fc36e003b76a570ba59ee5ba8cf495e76bb285c51',
}


class CharacterChatTokenizer:
    """Explicit unit-test tokenizer; never reported as model token usage."""
    label = 'unit-test:characters'
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        text = '\n'.join(item['role'] + ':' + item['content'] for item in messages) + '\nassistant:'
        return list(text.encode('utf-8')) if tokenize else text
