"""Read-only retrieval prerequisite probe; invoked by the existing command recorder."""
from pathlib import Path
import importlib.metadata
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.graph.token_counter import LocalTokenizerCounter
from vgar.evaluation.retrieval.evidence import sha256

counter = LocalTokenizerCounter(ROOT / 'artifacts/m2/w5-w6/tokenizer_manifest.json')
head = subprocess.check_output(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
print(json.dumps({
    'python': sys.version, 'interpreter': sys.executable, 'head': head,
    'counter': counter.provenance, 'counter_label': counter.counter_label,
    'probe_count': counter('def repair(): return True'),
    'dependencies': {key: importlib.metadata.version(key) for key in
                     ('pytest', 'pydantic', 'tree-sitter', 'tree-sitter-python', 'pyarrow', 'tokenizers')},
    'disk_free_bytes': shutil.disk_usage(ROOT).free,
    'm2_test_hashes': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in sorted((ROOT / 'tests/m2').glob('*.py'))},
}, ensure_ascii=False, indent=2))
