"""Only approved path-only config relocation may differ from historical inputs."""
from pathlib import Path

from test_bootstrap import api


ROOT = Path(__file__).resolve().parents[1]


def test_freeze_accepts_approved_relocation_but_rejects_tamper(tmp_path, monkeypatch):
    module = api("b_inputs")
    original = (ROOT / "integration/originals/config/demo.json").read_bytes()
    target = tmp_path / "config/demo.json"
    target.parent.mkdir()
    target.write_bytes((ROOT / "config/demo.json").read_bytes())
    backup = tmp_path / "integration/originals/config/demo.json"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(original)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    check = getattr(module, "frozen_input_matches", None)
    assert callable(check), "Relocated freeze input adapter is not implemented"
    assert check(target, original) is True
    target.write_bytes(target.read_bytes() + b" ")
    assert check(target, original) is False


def test_freeze_rejects_fake_original_and_unchanged_paths_still_work(tmp_path, monkeypatch):
    module = api("b_inputs")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    target = tmp_path / "config/demo.json"
    target.parent.mkdir()
    target.write_bytes((ROOT / "config/demo.json").read_bytes())
    backup = tmp_path / "integration/originals/config/demo.json"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"fake baseline")
    check = getattr(module, "frozen_input_matches", None)
    assert callable(check), "Relocated freeze input adapter is not implemented"
    assert check(target, b"fake baseline") is False
    assert check(target, target.read_bytes()) is True
