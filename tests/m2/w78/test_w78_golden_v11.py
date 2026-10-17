"""Fake-mode V11 runs must reproduce the saved 2026-10-15 real-model evidence byte for byte."""
import hashlib

import pytest

from w78_support import REPO

CASES = [
    ("A", "single_file_login", "b39baa82f293cf18185df8b3fa227f7d9fdddf5f1e3bda0064fb05e712dada02", 1299),
    ("B", "multi_file_invoice", "4f234c251402dbbfb6f6cdc3d4838d29fc81757c38260aa53b1d0b06de90f326", 1769),
    ("C", "missing_links", "c37a5ef27071c9635baba914fdf95408610a729f138fbe59a3df8e85bf07a3d3", 1169),
]


@pytest.mark.xfail(strict=True, reason="pipeline not migrated yet")
@pytest.mark.parametrize("letter,case,prompt_sha,tokens", CASES)
def test_v11_fake_run_reproduces_saved_real_evidence(letter, case, prompt_sha, tokens, tmp_path):
    from vgar.graph.token_counter import LocalTokenizerCounter
    from vgar.models.generator import FakeGenerator
    from vgar.models.huggingface.local_chat import LocalChatTokenizer
    from vgar.repair.config import CONFIG_DIR, load_config, load_task
    from vgar.repair.pipeline import run_repair
    golden = REPO / "tests/fixtures/m2/golden_v11" / letter
    policy, profile = load_config(CONFIG_DIR / "demo.json")
    task = load_task(REPO / "examples/m2/tasks" / f"{case}.json")
    run = run_repair(task, policy, FakeGenerator((golden / "raw_model_output.txt").read_text(encoding="utf-8")),
                     None, tmp_path / "runs", m1_counter=LocalTokenizerCounter(profile.tokenizer_manifest),
                     tokenizer=LocalChatTokenizer(profile.tokenizer_manifest), temp_root=tmp_path / "ws")
    assert run.record["status"] == "PASS"
    assert run.record["stages"]["prompt"]["input_tokens"] == tokens
    assert (run.directory / "prompt.txt").read_bytes() == (golden / "prompt.txt").read_bytes()
    assert hashlib.sha256((run.directory / "prompt.txt").read_bytes()).hexdigest() == prompt_sha
    assert (run.directory / "applied.diff").read_bytes() == (golden / "applied.diff").read_bytes()
