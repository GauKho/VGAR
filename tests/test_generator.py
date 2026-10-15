from test_bootstrap import api


def test_fake_generation_is_explicit_and_never_real(m1_case):
    from conftest import CharacterChatTokenizer
    task, counter = m1_case
    handoff = api('context_adapter').load_handoff(task, counter, counter.counter_label)
    prompt = api('prompt').build_repair_prompt(task, handoff, {}, CharacterChatTokenizer(), api('contracts').RepairPolicy())
    result = api('generator').FakeGenerator('--- a/auth.py\n').generate(prompt, None, 1)
    assert result['mode'] == 'fake' and result['raw_text'] == '--- a/auth.py\n'
    assert result['output_tokens'] is None and result['status'] == 'PASS'


def test_worker_timeout_and_invalid_json_never_fallback(tmp_path):
    module = api('model_worker')
    import sys
    result = module.invoke_worker((sys.executable, '-c', 'import time; time.sleep(10)'),
        tmp_path, tmp_path / 'response.json', .2)
    assert result['status'] == 'ERROR' and result['command']['timed_out']
    response = tmp_path / 'response.json'
    response.write_text('{}', encoding='utf-8')
    result = module.invoke_worker((sys.executable, '-c', 'pass'), tmp_path, response, 5)
    assert result['status'] == 'ERROR'

