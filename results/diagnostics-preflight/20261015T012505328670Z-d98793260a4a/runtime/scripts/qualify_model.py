"""Short real invocation qualifier; NOT a repair success or benchmark."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from vgar_m2_w78.config import load_config
from vgar_m2_w78.evidence import begin_run
from vgar_m2_w78.generator_hf import HFGenerator, HFChatTokenizer
from vgar_m2_w78.prompt import PromptArtifact
from vgar_m2_w78.evidence import digest

if __name__ == '__main__':
    policy, profile = load_config(ROOT / 'config/demo.json')
    run = begin_run(ROOT / 'results/qualification', 'real-short-invocation', mode='real', model=profile.model_dump(mode='json'))
    try:
        short = policy.model_copy(update={'output_cap': 16})
        generator = HFGenerator(profile, run.directory / 'workers', short)
        tokenizer = HFChatTokenizer(generator, short)
        messages = [{'role': 'user', 'content': 'Return only the word OK.'}]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        prompt = PromptArtifact(messages, rendered, len(ids), digest('qualifier'), digest(rendered), 'qualifier-not-repair', tokenizer.label)
        result = generator.generate(prompt, profile, policy.generation_timeout)
        run.stage('invocation', result)
        accepted = result['status'] == 'PASS' and result['raw_text'].strip() == 'OK' and not result['truncated']
        run.finish('PASS' if accepted else 'ERROR', scope='invocation_only_not_repair')
    except Exception as error:
        run.finish('ERROR', reason=str(error))
    print(run.path)
    raise SystemExit(0 if run.record['status'] == 'PASS' else 2)
