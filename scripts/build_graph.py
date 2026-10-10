from __future__ import annotations

import argparse
import json
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a JSON document using the frozen VGAR graph contract."
    )
    parser.add_argument("repository", help="Python repository root")
    parser.add_argument("output", help="Destination graph JSON")
    parser.add_argument("--repo-key", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()

    builder = PythonGraphBuilder(
        repo_key=args.repo_key,
        repository_revision=args.revision,

    )
    document = builder.build(args.repository)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Built {len(document['nodes'])} nodes and "
        f"{len(document['edges'])} edges -> {output_path}"
    )


if __name__ == "__main__":
    main()
