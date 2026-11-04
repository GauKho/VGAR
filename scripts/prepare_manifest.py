"""M2/M3: build a locked SWE-bench Verified manifest for ONE split (dev by default).

Examples (PowerShell, from the project root):
  python scripts/prepare_manifest.py . --count 25                       # dev pilot, multi-file only
  python scripts/prepare_manifest.py . --count 100 --min-source-files 1  # dev retrieval pool incl. single-file tasks
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.heldout_gate import freeze_sha256  # noqa: E402
from vgar.evaluation.retrieval.dataset import prepare_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a locked manifest for one split")
    parser.add_argument("root", type=Path, help="Project root (data/ is created here)")
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--split", choices=("dev", "heldout"), default="dev")
    parser.add_argument("--min-source-files", type=int, default=2, choices=(1, 2),
                        help="2 = multi-file only (pilot); 1 = also single-file tasks (pool)")
    parser.add_argument("--revision", help="40-char HF dataset revision to pin (default: current)")
    parser.add_argument("--allow-heldout", action="store_true", help="required for --split heldout")
    args = parser.parse_args()
    if args.split == "heldout" and not args.allow_heldout:
        parser.error("--split heldout requires --allow-heldout (record the decision in docs/research_design.md first)")
    freeze = None
    if args.split == "heldout":  # M3-W12-2: bind the manifest to the signed protocol freeze
        try:
            freeze = freeze_sha256(ROOT)
        except ValueError as error:
            parser.error(str(error))
    path, manifest = prepare_dataset(args.root, count=args.count, revision=args.revision, split=args.split,
                                     min_source_files=args.min_source_files, freeze_sha256=freeze)
    audit = manifest["selection_audit"]
    print(f"manifest: {path}")
    print(f"split={manifest['split']} tasks={len(manifest['tasks'])} raw_by_split={audit['raw_by_split']} "
          f"eligible={audit['eligible_count']} by_repo={audit['eligible_by_repo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
