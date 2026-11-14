"""L4-2 refactoring detection: ast exact-body pairs and the RefactoringMiner adapter (no Java started)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from git_fixture import linear_repo

from vgar.graph.ast_diff import read_python_blobs
from vgar.graph.history import read_commit_history
from vgar.graph.refactorings import (
    RefactoringMinerConfig,
    SymbolRef,
    ast_refactorings,
    detect_refactorings,
    parse_refactoringminer_json,
)

pytest.importorskip("dulwich")
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graphdiff" / "rm"

SHIPPING_BEFORE = b"import datetime\n\n\ndef estimate_delivery(order_date, days):\n    return order_date + days\n"
SHIPPING_AFTER = SHIPPING_BEFORE.replace(b"estimate_delivery(", b"estimate_delivery_date(")
NOTIFIER = b"class Notifier:\n    def send(self, text):\n        return text\n"
MESSAGING_BEFORE = b"\n\n\n\ndef quote(x):\n    return x * 2 + 1\n"
MESSAGING_AFTER = NOTIFIER + b"\ndef quote(x):\n    return _fee(x)\n\ndef _fee(x):\n    return x * 2 + 1\n"


def _fixture(name: str, ids: dict[str, str]) -> dict:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    for key, value in ids.items():
        text = text.replace(key, value)
    return json.loads(text)


def test_ast_detector_rename_function():
    refs = ast_refactorings({"m.py": (b"def old(a):\n    return a + 1\n", b"def new(a):\n    return a + 1\n")})
    ref, = refs
    assert (ref.detector, ref.family, dict(ref.renames)) == ("ast", "rename_method", {"new": "old"})
    assert ref.before == (SymbolRef("m.py", "old"),) and ref.after == (SymbolRef("m.py", "new"),)


def test_ast_detector_move_function_across_files():
    body = b"def f(a):\n    return a * 3\n"
    ref, = ast_refactorings({"a.py": (body, b""), "b.py": (None, body)})
    assert ref.family == "move_method" and ref.after == (SymbolRef("b.py", "f"),)


def test_ast_detector_class_rename_carries_members():
    before = b"class Old:\n    def m(self):\n        return 1\n"
    ref, = ast_refactorings({"c.py": (before, before.replace(b"Old", b"New"))})
    assert ref.family == "rename_class"
    assert {SymbolRef("c.py", "Old.m"), SymbolRef("c.py", "New.m")} <= ref.involved


def test_family_of_class_and_inline_variants():
    from vgar.graph.refactorings import family_of

    assert family_of("Move And Rename Class") == "move_class"
    assert family_of("Move And Rename Method") == "move_method"
    assert family_of("Move And Inline Method") == "inline_method"


def test_ast_detector_skips_unparsable_file():
    assert ast_refactorings({"bad.py": (b"print 'x'\n", b"print 'y'\n")}) == ()


def test_rm_json_rename_method_fixture():
    blobs = {"A": {"shop/services/shipping.py": (SHIPPING_BEFORE, SHIPPING_AFTER)}}
    result = parse_refactoringminer_json(_fixture("window.json", {"COMMIT_A": "A"}), blobs, "3.2.0")
    ref, = result["A"]
    assert (ref.detector, ref.family, ref.tool_version) == ("refactoringminer", "rename_method", "3.2.0")
    assert ref.before == (SymbolRef("shop/services/shipping.py", "estimate_delivery"),)
    assert ref.after == (SymbolRef("shop/services/shipping.py", "estimate_delivery_date"),)
    assert dict(ref.renames) == {"estimate_delivery_date": "estimate_delivery"}


def test_rm_paths_normalised_and_foreign_files_ignored():
    blobs = {"A": {"shop/services/shipping.py": (SHIPPING_BEFORE, SHIPPING_AFTER)}}
    ref, = parse_refactoringminer_json(_fixture("window.json", {"COMMIT_A": "A"}), blobs, None)["A"]
    assert all(symbol.path == "shop/services/shipping.py" for symbol in ref.involved)


def test_rm_json_move_class_and_extract_fixture():
    blobs = {"M": {"shop/notify.py": (NOTIFIER, None), "shop/messaging.py": (MESSAGING_BEFORE, MESSAGING_AFTER)}}
    move, extract = parse_refactoringminer_json(_fixture("move_class.json", {"COMMIT_M": "M"}), blobs, None)["M"]
    assert move.family == "move_class"
    assert {SymbolRef("shop/notify.py", "Notifier.send"), SymbolRef("shop/messaging.py", "Notifier.send")} <= move.involved
    assert extract.family == "extract_method"
    assert extract.after == (SymbolRef("shop/messaging.py", "_fee"),)  # "source ... after extraction" not an after symbol
    assert extract.before == (SymbolRef("shop/messaging.py", "quote"),)


def _shipping_repo(tmp_path: Path) -> tuple[Path, list[str]]:
    root = tmp_path / "repo"
    ids = linear_repo(root, [("base", {"shop/services/shipping.py": SHIPPING_BEFORE}),
                             ("rename estimate_delivery", {"shop/services/shipping.py": SHIPPING_AFTER}),
                             ("touch", {"shop/services/shipping.py": SHIPPING_AFTER + b"\nX = 1\n"})])
    return root, ids


def _window(root: Path, ids: list[str]):
    history = read_commit_history(root, revision=ids[-1], max_commits=2)
    blobs = {commit.commit_id: read_python_blobs(root, commit) for commit in history.commits}
    return history, blobs


def test_window_alignment_drops_non_window_commits_and_counts_missing(tmp_path):
    root, ids = _shipping_repo(tmp_path)
    history, blobs = _window(root, ids)
    output = tmp_path / "rm"
    output.mkdir()
    data = _fixture("window.json", {"COMMIT_A": ids[1]})
    (output / f"{ids[-1]}.json").write_text(json.dumps(data), encoding="utf-8")
    result = detect_refactorings(root, history, blobs, RefactoringMinerConfig(output=output))
    assert set(result) == {ids[1], ids[2]}
    assert result[ids[1]].detector == "refactoringminer" and result[ids[1]].refactorings[0].family == "rename_method"
    assert result[ids[1]].ast_refactorings and result[ids[1]].ast_refactorings[0].family == "rename_method"
    assert (result[ids[2]].detector, result[ids[2]].fallback_reason) == ("ast", "no output for commit")


def test_precomputed_per_commit_file_and_metadata_version(tmp_path):
    root, ids = _shipping_repo(tmp_path)
    history, blobs = _window(root, ids)
    output = tmp_path / "rm"
    output.mkdir()
    (output / f"{ids[1]}.json").write_text(json.dumps(_fixture("window.json", {"COMMIT_A": ids[1]})), encoding="utf-8")
    (output / "metadata.json").write_text('{"tool_version": "3.2.0"}', encoding="utf-8")
    result = detect_refactorings(root, history, blobs, RefactoringMinerConfig(output=output))
    assert result[ids[1]].refactorings[0].tool_version == "3.2.0"


def test_fallback_when_not_configured(tmp_path):
    root, ids = _shipping_repo(tmp_path)
    history, blobs = _window(root, ids)
    result = detect_refactorings(root, history, blobs, RefactoringMinerConfig())
    assert {(item.detector, item.fallback_reason) for item in result.values()} == {("ast", "not configured")}
    assert result[ids[1]].refactorings == result[ids[1]].ast_refactorings


def test_fallback_when_process_fails(tmp_path, monkeypatch):
    root, ids = _shipping_repo(tmp_path)
    history, blobs = _window(root, ids)
    home = tmp_path / "rmhome"
    (home / "lib").mkdir(parents=True)
    (home / "lib" / "RefactoringMiner-3.2.0.jar").write_bytes(b"")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom"))
    result = detect_refactorings(root, history, blobs, RefactoringMinerConfig(home=home, java_home=tmp_path))
    assert all(item.detector == "ast" and item.fallback_reason.startswith("process failed") for item in result.values())


def test_parse_warning_captured(tmp_path):
    root, ids = _shipping_repo(tmp_path)
    history, blobs = _window(root, ids)
    output = tmp_path / "rm"
    output.mkdir()
    (output / f"{ids[-1]}.json").write_text(json.dumps(_fixture("window.json", {"COMMIT_A": ids[1]})), encoding="utf-8")
    stderr = (FIXTURES / "window.stderr.txt").read_text(encoding="utf-8").replace("COMMIT_A", ids[1])
    (output / f"{ids[-1]}.stderr.txt").write_text(stderr, encoding="utf-8")
    result = detect_refactorings(root, history, blobs, RefactoringMinerConfig(output=output))
    assert len(result[ids[1]].parse_warnings) == 1 and "broken.py" in result[ids[1]].parse_warnings[0]
    assert result[ids[2]].parse_warnings == ()


def test_relative_env_path_rejected(monkeypatch):
    monkeypatch.setenv("VGAR_REFACTORINGMINER_OUTPUT", "relative/folder")
    with pytest.raises(ValueError):
        RefactoringMinerConfig.from_env()


def test_env_unset_gives_empty_config(monkeypatch):
    for name in ("VGAR_REFACTORINGMINER_HOME", "VGAR_JAVA_HOME", "VGAR_REFACTORINGMINER_OUTPUT"):
        monkeypatch.delenv(name, raising=False)
    assert RefactoringMinerConfig.from_env() == RefactoringMinerConfig()
