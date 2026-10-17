from vgar.models.huggingface import local_chat as m_local_chat
from w78_support import REPO


def test_local_chat_counts_full_qwen_template_without_model():
    tokenizer = m_local_chat.LocalChatTokenizer(REPO / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
    messages = [{'role': 'user', 'content': 'Return only the word OK.'}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    assert rendered == '<|im_start|>user\nReturn only the word OK.<|im_end|>\n<|im_start|>assistant\n'
    assert len(ids) > 1



def test_fake_mode_modules_do_not_import_torch():
    import subprocess
    import sys
    code = ('import sys, vgar.models.huggingface.local_chat, vgar.models.huggingface.generator_hf, '
            'vgar.models.generator; print("torch" in sys.modules)')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == 'False'
