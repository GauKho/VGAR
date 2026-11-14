"""L5-2 Daikon side: .dtrace writing with fixed declarations, output parsing on real Daikon 5.9.0 output."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from vgar.repair.daikon import (
    DaikonConfig,
    DaikonUnavailable,
    declarations,
    parse_invariants,
    parse_version,
    parse_violations,
    run_daikon,
    write_dtrace,
)
from vgar.repair.invariants import is_noise

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "invariants" / "daikon_5_9_0"
PPT = "shop.money.round_vnd(amount)"


def _pair(nonce: int, amount, result, test="t") -> list[dict]:
    base = {"ppt": PPT, "path": "shop/money.py", "qualname": "round_vnd", "nonce": nonce, "test": test}
    return [{**base, "kind": "enter", "vars": {"amount": amount}},
            {**base, "kind": "exit", "vars": {"amount": amount, "return": result}}]


def test_candidate_with_other_type_uses_baseline_declarations(tmp_path):
    base = _pair(1, 1.5, 2) + _pair(2, 90000.0, 90000)
    decls = declarations(base)
    write_dtrace(_pair(3, 1, 1), tmp_path / "cand.dtrace", decls)  # int where the baseline saw float: still double
    text = (tmp_path / "cand.dtrace").read_text(encoding="utf-8")
    assert "variable amount\n  var-kind variable\n  dec-type double\n  rep-type double" in text
    assert "shop.money.round_vnd(amount):::ENTER\nthis_invocation_nonce\n3\namount\n1\n1" in text
    write_dtrace(_pair(4, "x", 1), tmp_path / "odd.dtrace", decls)  # another type entirely
    assert "amount\nnonsensical\n2" in (tmp_path / "odd.dtrace").read_text(encoding="utf-8")


def test_is_none_flags_declared(tmp_path):
    ppt = "shop.discounts.discount_amount(subtotal, code)"
    meta = {"ppt": ppt, "path": "shop/discounts.py", "qualname": "discount_amount", "test": "t"}
    records = [{**meta, "nonce": 1, "kind": "enter", "vars": {"subtotal": 5, "code": None}},
               {**meta, "nonce": 2, "kind": "enter", "vars": {"subtotal": 6, "code": "SAVE10"}}]
    write_dtrace(records, tmp_path / "b.dtrace", declarations(records))
    text = (tmp_path / "b.dtrace").read_text(encoding="utf-8")
    assert "variable code_is_none\n  var-kind variable\n  dec-type boolean\n  rep-type int" in text
    assert "code\nnull\n1\nsubtotal\n5\n1\ncode_is_none\n1\n1" in text
    assert 'code\n"SAVE10"\n1\nsubtotal\n6\n1\ncode_is_none\n0\n1' in text
    assert "ppt shop.discounts.discount_amount(subtotal,\\_code):::ENTER" in text


def test_parse_invariants_counts_fixture():
    learned = parse_invariants((FIXTURES / "base_invariants.txt").read_text(encoding="utf-8"))
    assert len(learned) == 58
    assert "shop.catalog.get_product(sku):::EXIT  return.sku == orig(sku)" in learned


def test_parse_violations_merges_exit_duplicates():
    m7 = parse_violations((FIXTURES / "check_M7.txt").read_text(encoding="utf-8"))
    assert len(m7) == 10 and len([v for v in m7 if not is_noise(v)]) == 6
    assert parse_violations((FIXTURES / "check_R1.txt").read_text(encoding="utf-8")) == []
    m5, = parse_violations((FIXTURES / "check_M5.txt").read_text(encoding="utf-8"))
    assert m5.startswith("shop.catalog.get_product(sku):::EXIT  return.name one of")


def test_parse_version():
    assert parse_version((FIXTURES / "daikon_stdout_head.txt").read_text(encoding="utf-8")) == "5.9.0"


def test_run_daikon_unconfigured_raises(tmp_path):
    with pytest.raises(DaikonUnavailable):
        run_daikon(DaikonConfig(), tmp_path / "b", tmp_path / "c", tmp_path, time.monotonic() + 60)


def test_run_daikon_nonzero_exit_raises(tmp_path, monkeypatch):
    jar = tmp_path / "daikon.jar"
    jar.write_bytes(b"")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom"))
    with pytest.raises(DaikonUnavailable, match="exit 1"):
        run_daikon(DaikonConfig(jar=jar, java_home=tmp_path), tmp_path / "b", tmp_path / "c", tmp_path,
                   time.monotonic() + 60)


def test_run_daikon_past_deadline_raises(tmp_path):
    jar = tmp_path / "daikon.jar"
    jar.write_bytes(b"")
    with pytest.raises(DaikonUnavailable, match="deadline"):
        run_daikon(DaikonConfig(jar=jar, java_home=tmp_path), tmp_path / "b", tmp_path / "c", tmp_path,
                   time.monotonic() - 1)


def test_relative_env_path_rejected(monkeypatch):
    monkeypatch.setenv("VGAR_DAIKON_JAR", "relative/daikon.jar")
    with pytest.raises(ValueError):
        DaikonConfig.from_env()


def test_env_unset_gives_unconfigured(monkeypatch):
    monkeypatch.delenv("VGAR_DAIKON_JAR", raising=False)
    monkeypatch.delenv("VGAR_JAVA_HOME", raising=False)
    assert not DaikonConfig.from_env().configured
