import argparse
import json
from pathlib import Path

from .bootstrap import ROOT, verify_reference
from .config import load_config
from .contracts import RepairTask
from .evidence import begin_run
from .generator import FakeGenerator
from .pipeline import run_repair


def main(argv=None):
    parser = argparse.ArgumentParser(description='One-pass M2 trusted-fixture repair; no benchmark/MCP/training.')
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/demo.json')
    parser.add_argument('--mode', choices=('fake', 'real'), required=True)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'results/repair')
    parser.add_argument('--keep-workspace', action='store_true')
    parser.add_argument('--supersedes-run-id')
    parser.add_argument('--rerun-reason')
    args = parser.parse_args(argv)
    try:
        verify_reference()
        if bool(args.supersedes_run_id) != bool(args.rerun_reason):
            raise ValueError('Manual rerun requires both prior run ID and reason')
        from vgar.graph.token_counter import LocalTokenizerCounter
        path = args.task.resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        for key in ('source_repo', 'bundle_directory'):
            data[key] = (path.parent / data[key]).resolve()
        task = RepairTask.model_validate(data)
        policy, profile = load_config(args.config)
        counter = LocalTokenizerCounter(profile.tokenizer_manifest)
        if args.mode == 'fake':
            from .local_chat import LocalChatTokenizer
            generator = FakeGenerator((ROOT / 'tests/fixtures/reference_patches' / (task.task_id+'.diff')).read_text(encoding='utf-8'))
            tokenizer = LocalChatTokenizer(profile.tokenizer_manifest)
        else:
            from .generator_hf import HFGenerator, HFChatTokenizer
            generator = HFGenerator(profile, args.output_root / 'model-workers', policy)
            tokenizer = HFChatTokenizer(generator, policy)
        result = run_repair(task, policy, generator, None, args.output_root,
            m1_counter=counter, tokenizer=tokenizer, profile=profile if args.mode == 'real' else None,
            keep_workspace=args.keep_workspace, supersedes_run_id=args.supersedes_run_id, rerun_reason=args.rerun_reason)
    except Exception as error:
        result = begin_run(args.output_root, 'repair-config-error', mode=args.mode,
            requested_task=str(args.task), requested_config=str(args.config))
        result.finish('ERROR', reason=str(error), error_type=type(error).__name__)
    print(result.path)
    return {'PASS': 0, 'FAIL': 1, 'ERROR': 2}[result.record['status']]

