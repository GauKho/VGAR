"""Spike L1-1: run tree-sitter-graph (python.tsg) on a repo and diff it against PythonGraphBuilder.

Usage:
  python spikes/tree_sitter_graph/compare.py --repo D:/kltn/vgar-demo-shop/vgar-demo-shop \
      --tsg-exe <path/to/tree-sitter-graph> --tree-sitter-dir <dir holding config.json> --out <out dir>

config.json in --tree-sitter-dir must list the folder that contains a tree-sitter-python
v0.23.6 checkout under "parser-directories" (tree-sitter-graph 0.12 links tree-sitter 0.24, ABI <= 14).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from vgar.graph.builder import PythonGraphBuilder, discover_python_files

HERE = Path(__file__).resolve().parent


def run_tsg(repo: Path, exe: str, ts_dir: str, out: Path) -> dict[str, Any]:
    env = {**os.environ, "TREE_SITTER_DIR": ts_dir, "TREE_SITTER_LIBDIR": str(Path(ts_dir) / "lib")}
    graphs = {}
    for file in discover_python_files(repo):
        rel = file.relative_to(repo).as_posix()
        target = out / "tsg" / (rel.replace("/", "__") + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = [exe, str(HERE / "python.tsg"), str(file), "--scope", "source.python",
               "--json", "--output", str(target), "--global", f"FILE_PATH={rel}"]
        done = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise SystemExit(f"tree-sitter-graph failed on {rel}:\n{done.stderr}")
        graphs[rel] = json.loads(target.read_text(encoding="utf-8"))
    return graphs


def _value(raw: Any) -> Any:
    """Unwrap tree-sitter-graph's typed JSON values, e.g. {"type": "string", "string": "x"}."""
    if isinstance(raw, dict) and "type" in raw and len(raw) == 2:
        return next(v for k, v in raw.items() if k != "type")
    return raw


def tsg_facts(graphs: dict[str, Any]) -> tuple[list[dict], list[tuple[dict, dict, str]]]:
    nodes, edges = [], []
    for graph in graphs.values():
        items = graph["nodes"] if isinstance(graph, dict) else graph
        by_id = {item["id"]: {k: _value(v) for k, v in item.get("attrs", {}).items()} for item in items}
        file_edges = [(by_id[item["id"]], by_id[edge["sink"]], _value(edge.get("attrs", {}).get("type")))
                      for item in items for edge in item.get("edges", [])]
        # Excluded: the "Discard" sink and @overload stubs (skipped by PythonGraphBuilder).
        # What they own (CallSite/Field) is dropped too, with the edges.
        excluded = {id(a) for a in by_id.values()
                    if a.get("type") in {None, "Discard"} or a.get("overload")}
        excluded |= {id(dst) for src, dst, kind in file_edges
                     if kind in {"HAS_CALLSITE", "HAS_FIELD"} and id(src) in excluded}
        nodes.extend(a for a in by_id.values() if id(a) not in excluded)
        edges.extend(e for e in file_edges if id(e[0]) not in excluded and id(e[1]) not in excluded)
    return nodes, edges


def builder_facts(repo: Path) -> tuple[list[dict], list[tuple[dict, dict, str]]]:
    doc = PythonGraphBuilder(repo_key="spike", repository_revision="spike", source_roots=(".",)).build(repo)
    kind = {"Class": "Class", "Method": "Method", "Function": "Function", "Test": "Function", "CallSite": "CallSite"}
    by_id = {n["id"]: {"type": kind[n["type"]], "name": n["name"], "path": n["path"],
                       "line": n["range"]["start_line"]}
             for n in doc["nodes"] if n["type"] in kind}
    # A Test directly inside a class (pytest test method) is a Method syntactically.
    for e in doc["edges"]:
        if e["type"] == "CONTAINS" and by_id.get(e["source_id"], {}).get("type") == "Class":
            target = by_id.get(e["target_id"])
            if target and target["type"] == "Function":
                target["type"] = "Method"
    edges = []
    for e in doc["edges"]:
        src, dst = by_id.get(e["source_id"]), by_id.get(e["target_id"])
        if e["type"] == "CONTAINS" and src and dst:
            if src["type"] == "Class" and dst["type"] == "Method":
                edges.append((src, dst, "HAS_METHOD"))
            elif dst["type"] == "CallSite":
                edges.append((src, dst, "HAS_CALLSITE"))
    return list(by_id.values()), edges


def node_key(n: dict) -> tuple:
    return (n["type"], n["path"], n["name"], n["line"])


def edge_key(e: tuple[dict, dict, str]) -> tuple:
    return (e[2], e[0]["path"], e[0]["name"], e[1]["name"], e[1]["line"])


def diff(label: str, left: Counter, right: Counter) -> dict[str, Any]:
    only_tsg, only_builder = left - right, right - left
    print(f"{label:<14} tsg={sum(left.values()):>4} builder={sum(right.values()):>4} "
          f"match={sum((left & right).values()):>4} only_tsg={sum(only_tsg.values())} "
          f"only_builder={sum(only_builder.values())}")
    return {"only_tsg": sorted(map(list, only_tsg.elements())),
            "only_builder": sorted(map(list, only_builder.elements()))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--tsg-exe", required=True)
    parser.add_argument("--tree-sitter-dir", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    t_nodes, t_edges = tsg_facts(run_tsg(args.repo.resolve(), args.tsg_exe, args.tree_sitter_dir, args.out))
    b_nodes, b_edges = builder_facts(args.repo.resolve())

    report: dict[str, Any] = {}
    for kind in ("Class", "Function", "Method", "CallSite"):
        report[kind] = diff(kind, Counter(node_key(n) for n in t_nodes if n["type"] == kind),
                            Counter(node_key(n) for n in b_nodes if n["type"] == kind))
    for kind in ("HAS_METHOD", "HAS_CALLSITE"):
        report[kind] = diff(kind, Counter(edge_key(e) for e in t_edges if e[2] == kind),
                            Counter(edge_key(e) for e in b_edges if e[2] == kind))
    # Builder has no Field/GlobalVariable node types yet (schema.py NODE_TYPES): list TSG output only.
    for kind in ("GlobalVariable", "Field"):
        report[kind] = sorted({node_key(n) for n in t_nodes if n["type"] == kind})
        print(f"{kind:<14} tsg={len(report[kind]):>4} (builder has no such node type)")
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
