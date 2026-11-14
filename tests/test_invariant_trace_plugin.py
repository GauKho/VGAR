"""L5-1 trace plugin: records entry/exit/raise of workspace functions during pytest, outside the workspace."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

MODULE = '''from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    name: str
    price: int


def make(name, price):
    return Item(name, price)


def check(value):
    if value < 0:
        raise ValueError("negative")
    return value * 2


def hot(n):
    return n + 1


class Odd:
    __slots__ = ("a",)

    def __init__(self):
        self.a = 1

    @property
    def broken(self):
        raise RuntimeError("no")


def take(obj):
    return 1


class Proxy:
    def __getattribute__(self, name):
        raise RuntimeError("working outside of context")


def loop_last(values):
    total = []
    for value in values:
        total.append(value)
'''

TESTS = '''import pytest

from pkg.mod import Odd, Proxy, check, hot, loop_last, make, take


def test_make():
    assert make("pen", 3).price == 3


def test_check():
    assert check(2) == 4
    with pytest.raises(ValueError):
        check(-1)


def test_hot():
    for i in range(1500):
        hot(i)


def test_odd():
    assert take(Odd()) == 1


def test_proxy():
    assert take(Proxy()) == 1


def test_loop_last():
    assert loop_last(iter([1, 2])) is None
'''


def _repo(root: Path) -> Path:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "mod.py").write_text(MODULE, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_mod.py").write_text(TESTS, encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\ntestpaths = tests\npythonpath = .\n", encoding="utf-8")
    return root


def _run(repo: Path, trace: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "-p", "vgar.repair.invariant_trace_plugin", f"--vgar-trace-dir={trace}"],
                          cwd=repo, env=env, capture_output=True, text=True, check=False)


def _records(trace: Path) -> list[dict]:
    return [json.loads(line) for line in (trace / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def _traced(tmp_path: Path) -> tuple[Path, list[dict], dict]:
    repo, trace = _repo(tmp_path / "repo"), tmp_path / "trace"
    process = _run(repo, trace)
    assert process.returncode == 0, process.stdout + process.stderr
    return repo, _records(trace), json.loads((trace / "trace_meta.json").read_text(encoding="utf-8"))


def test_records_enter_exit_and_raise(tmp_path):
    _, records, _ = _traced(tmp_path)
    check = [r for r in records if r["qualname"] == "check"]
    assert {r["kind"] for r in check} == {"enter", "exit", "raise"}
    raised, = [r for r in check if r["kind"] == "raise"]
    assert raised["exception"] == "ValueError" and raised["vars"]["value"] == -1
    assert check[0]["ppt"] == "pkg.mod.check(value)" and check[0]["path"] == "pkg/mod.py"


def test_object_fields_and_stable_ids(tmp_path):
    _, first, _ = _traced(tmp_path / "a")
    _, second, _ = _traced(tmp_path / "b")
    exit_a = next(r for r in first if r["qualname"] == "make" and r["kind"] == "exit")
    exit_b = next(r for r in second if r["qualname"] == "make" and r["kind"] == "exit")
    assert exit_a["vars"]["return.price"] == 3 and exit_a["vars"]["return.name"] == "pen"
    assert exit_a["vars"]["return"]["__id__"] == exit_b["vars"]["return"]["__id__"]


def test_test_files_and_generated_code_not_traced(tmp_path):
    _, records, _ = _traced(tmp_path)
    assert all(r["path"] == "pkg/mod.py" for r in records)
    assert not any(r["qualname"].endswith("__init__") and "Item" in r["qualname"] for r in records)


def test_nothing_written_in_workspace(tmp_path):
    repo = _repo(tmp_path / "repo")
    before = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if "__pycache__" not in p.parts)
    assert _run(repo, tmp_path / "trace").returncode == 0
    after = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if "__pycache__" not in p.parts)
    assert before == after


def test_samples_capped_per_point(tmp_path):
    _, records, meta = _traced(tmp_path)
    assert sum(1 for r in records if r["qualname"] == "hot" and r["kind"] == "exit") == 1000
    assert meta["truncated"] is True and meta["records"] == len(records)


def test_tracer_survives_odd_objects(tmp_path):
    _, records, _ = _traced(tmp_path)
    take = next(r for r in records if r["qualname"] == "take" and r["kind"] == "enter")
    assert take["vars"]["obj"]["__object__"] == "Odd"


def test_records_carry_test_nodeid(tmp_path):
    _, records, _ = _traced(tmp_path)
    assert {r["test"] for r in records if r["qualname"] == "make"} == {"tests/test_mod.py::test_make"}


def test_hostile_object_never_breaks_the_test(tmp_path):
    _, records, _ = _traced(tmp_path)  # asserts pytest exit code 0
    assert any(r["qualname"] == "take" for r in records)


def test_loop_as_last_statement_is_a_normal_exit(tmp_path):
    _, records, _ = _traced(tmp_path)
    assert {r["kind"] for r in records if r["qualname"] == "loop_last"} == {"enter", "exit"}
