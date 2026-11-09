"""L2-1: boot.py, the entry point of the JARVIS image; everything but the JARVIS call itself runs without Docker."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BOOT_PATH = Path(__file__).parent.parent / "src" / "vgar" / "graph" / "jarvis" / "boot.py"
spec = importlib.util.spec_from_file_location("jarvis_boot", BOOT_PATH)
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


@pytest.mark.parametrize("bad_name", ["a.py", "m.py", "z.py"], ids=["first", "middle", "last"])
def test_syntax_error_is_skipped_at_any_position(tmp_path: Path, bad_name: str) -> None:
    for name in ("a.py", "m.py", "z.py"):
        (tmp_path / name).write_text("def broken(:\n" if name == bad_name else "x = 1\n", encoding="utf-8")
    good, skipped = boot.parsable_files(tmp_path)
    assert skipped == [bad_name] and bad_name not in [path.name for path in good] and len(good) == 2


def test_files_are_sorted_and_skipped_paths_are_posix(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "z.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.py").write_text("def broken(:\n", encoding="utf-8")
    good, skipped = boot.parsable_files(tmp_path)
    assert skipped == ["pkg/b.py"] and [path.relative_to(tmp_path).as_posix() for path in good] == ["pkg/a.py", "z.py"]


def test_match_statement_is_parsable(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("match v:\n    case 1:\n        pass\n", encoding="utf-8")
    good, skipped = boot.parsable_files(tmp_path)
    assert [path.name for path in good] == ["a.py"] and skipped == []


@pytest.mark.skipif(sys.version_info >= (3, 12), reason="this syntax is valid from Python 3.12")
def test_new_syntax_is_skipped_on_this_python(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f[T](x):\n    return x\n", encoding="utf-8")
    assert boot.parsable_files(tmp_path) == ([], ["a.py"])


def test_non_utf8_file_is_read_like_jarvis(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_bytes(b"# caf\xe9\nx = 1\n")
    good, skipped = boot.parsable_files(tmp_path)
    assert [path.name for path in good] == ["a.py"] and skipped == []


def test_nul_byte_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_bytes(b"x = 1\0\n")
    assert boot.parsable_files(tmp_path) == ([], ["a.py"])


@pytest.mark.parametrize("terms", [300, 5000], ids=["too-deep-for-jarvis", "too-deep-for-the-parser"])
def test_very_deep_expression_is_skipped(tmp_path: Path, terms: int) -> None:
    (tmp_path / "deep.py").write_text("def f(a):\n    return " + " + ".join(["a"] * terms) + "\n", encoding="utf-8")
    (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
    good, skipped = boot.parsable_files(tmp_path)
    assert skipped == ["deep.py"] and [path.name for path in good] == ["good.py"]


def test_expression_below_the_depth_limit_is_kept(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f(a):\n    return " + " + ".join(["a"] * 100) + "\n", encoding="utf-8")
    assert [path.name for path in boot.parsable_files(tmp_path)[0]] == ["a.py"]


def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    source, out = tmp_path / "src", tmp_path / "out"
    source.mkdir()
    out.mkdir()
    return source, out


def test_main_writes_skipped_and_calls_analyze(tmp_path: Path) -> None:
    source, out = _dirs(tmp_path)
    (source / "good.py").write_text("x = 1\n", encoding="utf-8")
    (source / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    seen = []

    def analyze(files: list[Path], package: Path, output: Path) -> None:
        seen.append(([path.name for path in files], package, output))
        (output / "graph.json").write_text('{"good": []}', encoding="utf-8")

    assert boot.main(source, out, analyze) == 0
    assert seen == [(["good.py"], source, out)]
    assert json.loads((out / "skipped.json").read_text(encoding="utf-8")) == ["bad.py"]


def test_all_files_broken_writes_an_empty_graph(tmp_path: Path) -> None:
    source, out = _dirs(tmp_path)
    (source / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    def analyze(files: list[Path], package: Path, output: Path) -> None:
        raise AssertionError("JARVIS needs at least one file")

    assert boot.main(source, out, analyze) == 0
    assert json.loads((out / "graph.json").read_text(encoding="utf-8")) == {}


def test_chmod_runs_even_when_analyze_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, out = _dirs(tmp_path)
    (source / "good.py").write_text("x = 1\n", encoding="utf-8")
    opened = []
    monkeypatch.setattr(boot.os, "chmod", lambda path, mode: opened.append((Path(path).name, mode)))

    def analyze(files: list[Path], package: Path, output: Path) -> None:
        raise RuntimeError("JARVIS crashed")

    with pytest.raises(RuntimeError, match="JARVIS crashed"):
        boot.main(source, out, analyze)
    assert ("skipped.json", 0o777) in opened


def test_importlib_metadata_is_loaded_first() -> None:
    assert "importlib.metadata" in sys.modules
    assert BOOT_PATH.read_text(encoding="utf-8").index("import importlib.metadata") < BOOT_PATH.read_text(encoding="utf-8").index("import runpy")
