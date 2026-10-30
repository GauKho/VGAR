"""Pull official SWE-bench images for the first N tasks of an approved manifest and pin them by digest.

Writes the runtime config used by scripts/prepare_task_env.py (images keep manifest order, so they are
always a prefix of the population). Run in WSL with Docker reachable.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def image_repo(instance_id: str) -> str:
    return 'swebench/sweb.eval.x86_64.' + instance_id.replace('__', '_1776_')


def pin(manifest_path: Path, runtime_path: Path, *, limit: int) -> int:
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    config = json.loads(Path(runtime_path).read_text(encoding='utf-8'))
    images = dict(config['images'])
    for task in manifest['tasks'][:limit]:
        repo = image_repo(task['instance_id'])
        if task['instance_id'] in images:
            continue
        subprocess.run(['docker', 'pull', repo + ':latest'], check=True, capture_output=True, text=True)
        digests = json.loads(subprocess.run(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}',
                                             repo + ':latest'], check=True, capture_output=True, text=True).stdout)
        matching = [d for d in digests if d.startswith(repo + '@sha256:')]
        if len(matching) != 1:
            raise ValueError('Expected exactly one registry digest for ' + repo)
        images[task['instance_id']] = {'reference': matching[0], 'image_id': None}
        print('PINNED', matching[0], flush=True)
    order = [t['instance_id'] for t in manifest['tasks']]
    config['images'] = {key: images[key] for key in order if key in images}
    config['qualification_state'] = 'PINNED'
    Path(runtime_path).write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/m1/w10_dev_manifest.json')
    parser.add_argument('--runtime', type=Path, default=ROOT/'configs/m1/w10_task_env_profile.json')
    parser.add_argument('--limit', type=int, required=True)
    args = parser.parse_args(argv)
    return pin(args.manifest, args.runtime, limit=args.limit)


if __name__ == '__main__':
    sys.exit(main())
