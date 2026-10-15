from test_bootstrap import api
from conftest import VGAR


def test_local_chat_counts_full_qwen_template_without_model():
    tokenizer = api('local_chat').LocalChatTokenizer(VGAR / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
    messages = [{'role': 'user', 'content': 'Return only the word OK.'}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    assert rendered == '<|im_start|>user\nReturn only the word OK.<|im_end|>\n<|im_start|>assistant\n'
    assert len(ids) > 1

