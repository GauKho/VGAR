from __future__ import annotations

import argparse

from vgar.graph.sqlite_store import SQLiteGraphStore, load_graph_document


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and load a VGAR graph JSON document into SQLite."
    )
    parser.add_argument("document", help="Path to a VGAR graph JSON document")
    parser.add_argument("database", help="Destination SQLite database path")
    args = parser.parse_args()

    document = load_graph_document(args.document)
    store = SQLiteGraphStore(args.database)
    store.ingest(document)

    print(
        "Loaded graph",
        document["graph_version"],
        "into",
        args.database,
    )


if __name__ == "__main__":
    main()
