"""Component boundary kit for G1 (plan 2026-11-17 Task 3; spec §1.2).

  python scripts/g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components            # write the sheet
  python scripts/g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components --lock     # after labelling
  python scripts/g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components --score    # needs the lock

Graphs use the default served build (static, no optional layers), one task per repository of the G1 kit.
Exit codes: 0 done; 2 sheet missing, not locked, edited after the lock, or labels invalid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.evaluation.g1_components import (
    boundary_quality,
    read_component_sheet,
    sample_components,
    write_component_sheet,
)
from vgar.evaluation.g1_labels import sha256_file

TOP_EDGES = 10


def _documents(kit: Path) -> dict[str, dict]:
    from vgar.graph.builder import PythonGraphBuilder

    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    return {task["repo"]: PythonGraphBuilder(repo_key=task["task_id"], repository_revision=task["base_commit"])
            .build(Path(task["tree"])) for task in manifest["tasks"]}


def _markdown(sampled: list[dict], documents: dict[str, dict]) -> str:
    lines = ["# G1 · Component boundary labels", "",
             ("Label each Component in `components.csv`: `correct` (boundary right), `merge` (should join another "
              "component), `split` (holds more than one component)."), ""]
    for item in sampled:
        document = documents[item["repo"]]
        names = {n["id"]: n["qualified_name"] for n in document["nodes"] if n["type"] == "Component"}
        depends = [e for e in document["edges"] if e["type"] == "DEPENDS_ON" and e["source_id"] in names
                   and e["target_id"] in names]
        weight = lambda e: e["properties"].get("weight", 0)
        out = sorted((e for e in depends if e["source_id"] == item["component_id"]), key=weight, reverse=True)[:TOP_EDGES]
        into = sorted((e for e in depends if e["target_id"] == item["component_id"]), key=weight, reverse=True)[:TOP_EDGES]
        lines += [f"## `{item['name']}` · {item['repo']}", "", f"`{item['component_id']}`", "", "Files:", ""]
        lines += [f"- `{path}`" for path in item["files"]]
        lines += ["", "Depends on: " + (", ".join(f"`{names[e['target_id']]}` ({weight(e)})" for e in out) or "—"),
                  "", "Used by: " + (", ".join(f"`{names[e['source_id']]}` ({weight(e)})" for e in into) or "—"), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-repo", type=int, default=5)
    parser.add_argument("--lock", action="store_true")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args(argv)
    sheet, lock_file = args.out / "components.csv", args.out / "components_manifest.json"
    if not args.lock and not args.score:
        if sheet.exists():
            print(f"refused: {sheet} exists", file=sys.stderr)
            return 2
        args.out.mkdir(parents=True, exist_ok=True)
        documents = _documents(args.kit)
        sampled = sample_components(documents, per_repo=args.per_repo)
        write_component_sheet(sheet, sampled)
        (args.out / "components.md").write_text(_markdown(sampled, documents), encoding="utf-8")
        state = {"sampled_ids": sorted(item["component_id"] for item in sampled)}
        lock_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"{len(sampled)} components: {sheet}")
        return 0
    if not sheet.exists() or not lock_file.exists():
        print(f"refused: {sheet} or {lock_file} missing; write the sheet first", file=sys.stderr)
        return 2
    state = json.loads(lock_file.read_text(encoding="utf-8"))
    rows = read_component_sheet(sheet)
    if sorted(row["component_id"] for row in rows) != state["sampled_ids"]:  # dropped or added rows change n
        print("refused: components.csv rows differ from the sampled components", file=sys.stderr)
        return 2
    try:
        result = boundary_quality(rows)
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    if args.lock:
        if "sheet_sha256" in state:  # one lock only: re-locking after seeing a score would hide edits
            print("refused: components.csv is already locked", file=sys.stderr)
            return 2
        lock_file.write_text(json.dumps({**state, "sheet_sha256": sha256_file(sheet)}, indent=2), encoding="utf-8")
        print(f"locked {sheet}")
        return 0
    if state.get("sheet_sha256") != sha256_file(sheet):
        print("refused: components.csv is not locked or changed after the lock", file=sys.stderr)
        return 2
    (args.out / "component_quality.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
