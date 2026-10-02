from __future__ import annotations

import argparse
import json
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the graph for a real Python repository, ingest it into SQLite, "
            "and verify direct M1 GraphService queries before the MCP smoke test."
        )
    )

    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--repo-key", default="local/vgar")
    parser.add_argument("--revision", default="local-working-tree")
    parser.add_argument("--query", default="SQLiteGraphService")

    parser.add_argument(
        "--json-output",
        default="artifacts/real_repo_graph.json",
    )

    parser.add_argument(
        "--database",
        default="artifacts/real_repo_graph.db",
    )

    parser.add_argument(
        "--no-jedi",
        action="store_true",
    )

    args = parser.parse_args()

    repository = Path(args.repository).resolve()
    json_output = Path(args.json_output).resolve()
    database = Path(args.database).resolve()

    builder = PythonGraphBuilder(
        repo_key=args.repo_key,
        repository_revision=args.revision,
        use_jedi=not args.no_jedi,
    )

    document = builder.build(repository)

    json_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_output.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if database.exists():
        database.unlink()

    store = SQLiteGraphStore(database)
    store.ingest(document)

    service = SQLiteGraphService(store)

    summary = service.get_repository_summary()
    search = service.search_symbols(
        args.query,
        limit=20,
    )

    print(
        f"Built real repo graph: "
        f"nodes={summary.node_count}, "
        f"edges={summary.edge_count}"
    )

    print(f"JSON: {json_output}")
    print(f"SQLite: {database}")

    print(
        f"query={args.query!r}, "
        f"matches={len(search.symbols)}"
    )

    for symbol in search.symbols:
        print(
            f"  - {symbol.symbol_id} "
            f"[{symbol.path}]"
        )

    if not search.symbols:
        raise SystemExit(
            "Real-repo graph build succeeded, "
            "but the smoke query returned no symbols. "
            "Choose an existing class/function name with --query."
        )

    anchor = search.symbols[0].symbol_id

    node = service.get_node(anchor)
    callers = service.get_callers(anchor)
    callees = service.get_callees(anchor)

    if set(node.model_dump()) != {"repo"}:
        raise SystemExit(
            "GraphNode public contract is not "
            "wrapped by 'repo'."
        )

    print(
        "GraphNode contract: PASS ({repo: {...}})"
    )

    print(
        f"callers={len(callers.symbols)}, "
        f"callees={len(callees.symbols)}"
    )

    print(
        "Real repository M1 -> SQLite "
        "-> GraphService smoke PASS"
    )

    print()

    print(
        "Next, exercise the same database "
        "through MCP/LangChain:"
    )

    print(
        '  $env:VGAR_GRAPH_BACKEND="sqlite"'
    )

    print(
        f'  $env:VGAR_GRAPH_DATABASE="{database}"'
    )

    print(
        f'  python .\\scripts\\smoke_w3_w4.py '
        f'--query "{args.query}"'
    )


if __name__ == "__main__":
    main()