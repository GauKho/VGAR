"""Sinh config runner từ một template và bundle vừa export lại (M1-W12 spec §4.8).

  python scripts/derive_experiment_config.py --template configs/m3/w10_dev_stage1.json --data-root ~/w9 \
      --tasks astropy__astropy-13033,django__django-10914 --bundle-dir @data/w12/bundles/repair \
      --variants A0:bm25,A1:graph,A2:graph,A3:graph --out results/m1/w12/dry_run/<ts>/w12_dry_run.json

Tên variant An ánh xạ tới configs/m2/variants/An.json. Config sinh ra được kiểm bằng load_experiment;
không qua thì file đầu ra bị xóa và script trả mã lỗi.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.repair.derive_config import derive_config  # noqa: E402
from vgar.evaluation.repair.manifest import load_experiment  # noqa: E402

VARIANTS_DIR = ROOT / "configs/m2/variants"


def parse_variants(text: str, variants_dir: Path = VARIANTS_DIR) -> list[dict]:
    variants = []
    for item in filter(None, text.split(",")):
        name, _, arm = item.partition(":")
        path = variants_dir / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Variant {name}: {path} does not exist")
        variants.append({"path": str(path.resolve()), "arm": arm})
    return variants


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--tasks", required=True, help="comma-separated instance ids, in run order")
    parser.add_argument("--bundle-dir", required=True, help="@data/... directory holding <task>/{bm25,graph,graph.json}")
    parser.add_argument("--variants", required=True, help="comma-separated NAME:ARM, e.g. A0:bm25,A1:graph")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        template = json.loads(args.template.read_text(encoding="utf-8"))
        config = derive_config(template, template_dir=args.template.parent, data_root=args.data_root,
                               task_ids=[t for t in args.tasks.split(",") if t], bundle_dir=args.bundle_dir,
                               variants=parse_variants(args.variants))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        experiment = load_experiment(args.out, args.data_root)
    except Exception as error:  # noqa: BLE001 -- any rejection by the runner invalidates the config
        args.out.unlink()
        parser.exit(1, f"{parser.prog}: error: runner rejected the derived config: {type(error).__name__}: {error}\n")
    print(args.out, experiment.experiment_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
