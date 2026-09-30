from __future__ import annotations

from pathlib import Path

import pytest

from vgar.repair.workspace import create_workspace, fingerprint_source, safe_relative_path


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("secret", encoding="utf-8")
    return source


def test_copy_is_isolated_and_cleaned(tmp_path: Path) -> None:
    source = _source(tmp_path)
    original = fingerprint_source(source)
    with create_workspace(source, tmp_path / "temp") as lease:
        assert (lease.path / "src" / "app.py").read_text(encoding="utf-8") == "value = 1\n"
        assert not (lease.path / ".git").exists()
        (lease.path / "src" / "app.py").write_text("value = 2\n", encoding="utf-8")
        workspace_path = lease.path
        assert source.joinpath("src/app.py").read_text(encoding="utf-8") == "value = 1\n"
        assert lease.source_hash_before == original
    assert not workspace_path.exists()
    assert fingerprint_source(source) == original


def test_parent_traversal_and_absolute_selector_rejected() -> None:
    for path in ("../secret", "src/../../secret", "/tmp/secret", "C:/secret"):
        with pytest.raises(ValueError):
            safe_relative_path(path)


def test_external_symlink_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("do not read", encoding="utf-8")
    try:
        (source / "src" / "external.py").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available")
    with pytest.raises(ValueError, match="link"):
        create_workspace(source, tmp_path / "temp")


def test_large_source_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / "src" / "huge.bin").write_bytes(b"x" * 1024)
    with pytest.raises(ValueError, match="size"):
        create_workspace(source, tmp_path / "temp", max_file_bytes=512)
