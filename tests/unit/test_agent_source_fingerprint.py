"""M3-X2b (03/11): the agent host fingerprints the source like the engine, so repos with file symlinks
(django docs) are accepted instead of crashing with 'Source contains a link'."""
import os

import pytest

from vgar.agents.tool_agent import source_fingerprint


def _repo_with_file_link(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'docs').mkdir(parents=True)
    (repo / 'docs/real.png').write_bytes(b'png')
    try:
        os.symlink('real.png', repo / 'docs/alias.png')
    except (OSError, NotImplementedError):
        pytest.skip('symlinks not permitted on this machine')
    return repo


def test_matches_the_engine_source_hash(tmp_path):
    import json

    from vgar.repair.evidence import digest
    from vgar.repair.workspace import inventory
    repo = tmp_path / 'repo'
    (repo / 'pkg').mkdir(parents=True)
    (repo / 'pkg/a.py').write_text('x = 1\n', encoding='utf-8')
    # Same formula as the engine's EvidenceBundle.source_hash_after (repair/pipeline.py).
    assert source_fingerprint(repo) == digest(json.dumps(inventory(repo), sort_keys=True))


def test_file_symlink_is_accepted(tmp_path):
    repo = _repo_with_file_link(tmp_path)
    assert source_fingerprint(repo).startswith('sha256:')


def test_fingerprint_changes_when_a_file_changes(tmp_path):
    repo = _repo_with_file_link(tmp_path)
    before = source_fingerprint(repo)
    (repo / 'docs/real.png').write_bytes(b'changed')
    assert source_fingerprint(repo) != before


def test_directory_symlink_is_still_rejected(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'pkg').mkdir(parents=True)
    try:
        os.symlink('pkg', repo / 'alias', target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks not permitted on this machine')
    with pytest.raises(ValueError):
        source_fingerprint(repo)
