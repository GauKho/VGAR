"""vgar repair runs the one-pass M2 pipeline on each trusted fixture; bad input is an ERROR run."""
from pathlib import Path

import pytest

from vgar import cli
from w78_support import REPO


@pytest.mark.parametrize("case", ["single_file_login", "multi_file_invoice", "missing_links"])
def test_vgar_repair_fake_passes_each_fixture(case, tmp_path):
    code = cli.main(["repair", "--task", str(REPO / f"examples/m2/tasks/{case}.json"),
                     "--mode", "fake", "--output-root", str(tmp_path / "runs")])
    assert code == 0


def test_vgar_repair_missing_task_writes_error_run(tmp_path, capsys):
    code = cli.main(["repair", "--task", str(tmp_path / "missing.json"), "--mode", "fake",
                     "--output-root", str(tmp_path / "runs")])
    assert code == 2
    assert Path(capsys.readouterr().out.strip().splitlines()[-1]).is_file()
