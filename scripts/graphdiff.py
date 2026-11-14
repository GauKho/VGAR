"""GraphDiff (Layer 4) over a pinned first-parent window: graph edits, raw-diff baseline and summary.

The window ends at the graph's own revision (``repository_revision`` of the graph), never later.

Usage:
    python scripts/graphdiff.py <repo> --graph <graph.json | graph.db> [--graph-version V]
        [--max-commits 50] [--source-root src ...] [--rm-home DIR] [--java-home DIR] [--rm-output DIR]
        [--out DIR]

RefactoringMiner settings default to ``VGAR_REFACTORINGMINER_HOME``, ``VGAR_JAVA_HOME`` and
``VGAR_REFACTORINGMINER_OUTPUT``; without them the ``ast`` detector runs and every edit says so.
Default output: ``results/graphdiff/<repo folder>-<revision[:12]>/``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.graph.graphdiff import run_graphdiff
from vgar.graph.refactorings import RefactoringMinerConfig

logger = logging.getLogger("graphdiff")


def load_graph(path: Path, graph_version: str | None) -> dict:
    """Graph document from a JSON file or a SQLite graph database.

    Args:
        path: ``.json`` document or SQLite database.
        graph_version: Version inside the database; the single ready one when omitted.
    """
    if path.suffix.lower() == ".json":
        from vgar.graph.sqlite_store import load_graph_document

        return load_graph_document(path)
    from vgar.graph.sqlite_store import SQLiteGraphStore

    store = SQLiteGraphStore(path, graph_version=graph_version)
    return store.load_document(store.resolve_graph_version())


def _absolute(parser: argparse.ArgumentParser, value: str | None, name: str) -> Path | None:
    if value is None:
        return None
    if not Path(value).is_absolute():
        parser.error(f"{name} must be an absolute path")
    return Path(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--graph-version")
    parser.add_argument("--max-commits", type=int, default=50)
    parser.add_argument("--source-root", action="append", dest="source_roots")
    parser.add_argument("--rm-home")
    parser.add_argument("--java-home")
    parser.add_argument("--rm-output")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    config = RefactoringMinerConfig.from_env()
    overrides = {key: path for key, path in (("home", _absolute(parser, args.rm_home, "--rm-home")),
                                              ("java_home", _absolute(parser, args.java_home, "--java-home")),
                                              ("output", _absolute(parser, args.rm_output, "--rm-output")))
                 if path is not None}
    config = replace(config, **overrides)
    document = load_graph(args.graph, args.graph_version)
    roots = tuple(args.source_roots or ["src"])
    result = run_graphdiff(args.repo, document, max_commits=args.max_commits, source_roots=roots, rm_config=config)
    revision = result.summary["revision"]
    out = args.out or Path("results") / "graphdiff" / f"{args.repo.resolve().name}-{revision[:12]}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "graph_edits.jsonl").open("w", encoding="utf-8") as file:
        for edit in result.edits:
            file.write(json.dumps(edit.to_json(), ensure_ascii=False) + "\n")
    with (out / "raw_baseline.jsonl").open("w", encoding="utf-8") as file:
        for row in result.raw_baseline:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = dict(result.summary, command=[str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:])],
                   graph=str(args.graph), repo=str(args.repo.resolve()))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"out": str(out), "commits_read": summary["commits_read"], "edits_total": summary["edits_total"],
                      "edits_validated": summary["edits_validated"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
