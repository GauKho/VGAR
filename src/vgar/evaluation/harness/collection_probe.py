"""Target-side base-only pytest collection. Compatible with Python 3.5+.

Copied into a fresh owned container; no VGAR installation and no benchmark oracle.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback

PROTOCOL = 'vgar-pytest-collection-v1'


def git(root, args):
    return subprocess.check_output(['git', '-C', root]+args).decode('utf-8').strip()


def source_identity(root):
    raw = subprocess.check_output(['git', '-C', root, 'ls-files', '-z', '--', '*.py'])
    paths = sorted(p.decode('utf-8') for p in raw.split(b'\0') if p)
    inventory = []
    for relative in paths:
        path = os.path.join(root, relative)
        if os.path.islink(path) or not os.path.isfile(path):
            raise ValueError('Tracked Python inventory contains link/missing file')
        with open(path, 'rb') as stream:
            inventory.append([relative, hashlib.sha256(stream.read()).hexdigest()])
    digest = hashlib.sha256(json.dumps(inventory, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    return {'head': git(root, ['rev-parse', 'HEAD']),
            'clean': not bool(git(root, ['status', '--porcelain', '--untracked-files=no'])),
            'inventory_hash': 'sha256:'+digest, 'inventory_count': len(paths)}, set(paths)


class CollectionRecorder(object):
    def __init__(self):
        self.node_ids = []
        self.errors = []

    def pytest_collection_finish(self, session):
        self.node_ids = sorted(set(item.nodeid for item in session.items))

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(str(report.longrepr))


def run_probe(config):
    result = {'protocol': PROTOCOL, 'status': 'ERROR', 'reason': 'PROBE_ERROR',
        'source_before': None, 'source_after': None,
        'runtime': {'python': platform.python_version(), 'pytest': None, 'executable': sys.executable},
        'collection': {'exit_code': None, 'node_ids': [], 'errors': []}}
    cwd = os.getcwd()
    try:
        root = os.path.realpath(config['source_root'])
        before, paths = source_identity(root)
        result['source_before'] = before
        if before['head'] != config['base_commit'] or not before['clean'] or not paths:
            result['reason'] = 'BASE_SOURCE_MISMATCH'
            return result
        scope = config['scope']
        default_discovery = scope == ['@pytest-default']
        if not default_discovery and (not scope or len(scope) != len(set(scope)) or any(p not in paths for p in scope)):
            result['reason'] = 'SCOPE_NOT_IN_BASE_INVENTORY'
            return result
        os.chdir(root)
        try:
            import pytest
        except ImportError:
            result.update(status='EXCLUDED', reason='PYTEST_UNAVAILABLE')
            return result
        result['runtime']['pytest'] = pytest.__version__
        recorder = CollectionRecorder()
        code = int(pytest.main(['-q', '-p', 'no:cacheprovider', '--collect-only']+([] if default_discovery else scope), plugins=[recorder]))
        result['collection'] = {'exit_code': code, 'node_ids': recorder.node_ids, 'errors': recorder.errors}
        if code == 0 and recorder.node_ids and not recorder.errors:
            result.update(status='COLLECTED', reason=None)
        elif not recorder.node_ids and code in (0, 5) and not recorder.errors:
            result.update(status='EXCLUDED', reason='EMPTY_COLLECTION')
        else:
            result.update(status='EXCLUDED', reason='COLLECTION_FAILED')
    except BaseException:
        result['traceback'] = traceback.format_exc()
    finally:
        os.chdir(cwd)
        if result['source_before'] is not None:
            try:
                result['source_after'] = source_identity(config['source_root'])[0]
                if result['source_after'] != result['source_before']:
                    result.update(status='ERROR', reason='SOURCE_DRIFT')
            except BaseException:
                result.update(status='ERROR', reason='SOURCE_INTEGRITY_UNAVAILABLE', traceback=traceback.format_exc())
    return result


def main():
    with open(sys.argv[1]) as stream:
        config = json.load(stream)
    result = run_probe(config)
    fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
