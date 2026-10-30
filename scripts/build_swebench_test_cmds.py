"""Write configs/m1/swebench_410_test_cmds.json from the installed swebench (must be 4.1.0).

Run with an interpreter that has swebench==4.1.0, e.g. in WSL:
  ~/spike-swebench/bin/python scripts/build_swebench_test_cmds.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from vgar.evaluation.harness.test_cmds import TABLE_PATH, build_table  # noqa: E402


def main() -> int:
    import swebench
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    if swebench.__version__ != '4.1.0':
        raise SystemExit('swebench 4.1.0 required, found ' + swebench.__version__)
    table = build_table(MAP_REPO_VERSION_TO_SPECS, swebench_version=swebench.__version__)
    TABLE_PATH.write_text(json.dumps(table, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print('WROTE', TABLE_PATH, sum(len(v) for v in table['repos'].values()), 'repo versions')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
