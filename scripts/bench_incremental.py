"""M1-W12-1: bảng U1 (cold build vs warm incremental update) -> <out>/u1.json + <out>/u1.md.

  python scripts/bench_incremental.py --repo <data>/repositories/pydata__xarray-4629 --source-roots xarray \
      --out results/m1/w12/u1/<timestamp>
  python scripts/bench_incremental.py --fixture --repeats 3 --out <tmp>      # CI

The checkout passed to --repo is copied first and never modified.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.incremental_bench import MAX_REPEATS, environment_info, render_u1, run_bench  # noqa: E402

FIXTURE = {
    "src/a.py": "from b import f\n\ndef caller():\n    return f()\n",
    "src/b.py": "def f():\n    return 1\n\ndef g():\n    return f()\n",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", type=Path)
    source.add_argument("--fixture", action="store_true", help="tiny generated repository (CI)")
    parser.add_argument("--source-roots", default="src", help="comma-separated, relative to the repository")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= MAX_REPEATS:
        parser.error(f"--repeats must be between 1 and {MAX_REPEATS}")
    roots = tuple(r for r in args.source_roots.split(",") if r)
    with tempfile.TemporaryDirectory(prefix="vgar-u1-") as scratch:
        repo = args.repo
        if args.fixture:
            repo, roots = Path(scratch) / "fixture", ("src",)
            for relative, text in FIXTURE.items():
                (repo / relative).parent.mkdir(parents=True, exist_ok=True)
                (repo / relative).write_text(text, encoding="utf-8")
        result = run_bench(repo, roots, repeats=args.repeats, workdir=Path(scratch) / "work")
    result["environment"] = environment_info(ROOT)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "u1.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    (args.out / "u1.md").write_text(render_u1(result), encoding="utf-8")
    print(args.out / "u1.json")
    print(args.out / "u1.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
