"""M3-W12-3: kiểm mọi bảng trong Results draft có dòng `Nguồn:` (script tồn tại) hoặc `Đang chờ:`.

  python scripts/check_results_sources.py [docs/paper/results_draft_v1.md]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.results_sources import check_sources  # noqa: E402


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else ROOT / "docs/paper/results_draft_v1.md"
    errors = check_sources(path.read_text(encoding="utf-8"), ROOT)
    for error in errors:
        print(f"{path}: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
