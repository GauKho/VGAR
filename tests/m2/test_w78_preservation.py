"""Lossless-copy audit detects actual byte loss, not only file counts."""
import importlib.util
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/check_m2_integration.py"
    if not path.is_file():
        pytest.fail("Resumable M2 integrity auditor is not implemented")
    spec = importlib.util.spec_from_file_location("m2_integrity_check", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_auditor_detects_changed_and_missing_bytes(tmp_path):
    root = tmp_path / "copy"
    root.mkdir()
    (root / "one.txt").write_bytes(b"changed")
    expected = {
        "one.txt": {"size": 3, "sha256": "7692c3ad3540bb803c020b3aee66cd8887123234ea0c6e7143c0add73ff431ed"},
        "missing.txt": {"size": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    }
    result = module().compare_files(root, expected)
    assert result == {"changed": ["one.txt"], "missing": ["missing.txt"]}


def test_auditor_accepts_exact_bytes_and_validates_relocated_originals(tmp_path):
    (tmp_path / "one.txt").write_bytes(b"one")
    expected = {"one.txt": {"size": 3, "sha256": "7692c3ad3540bb803c020b3aee66cd8887123234ea0c6e7143c0add73ff431ed"}}
    assert module().compare_files(tmp_path, expected) == {"changed": [], "missing": []}
