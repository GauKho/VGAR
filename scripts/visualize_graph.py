from __future__ import annotations

import argparse
import json
from pathlib import Path

from vgar.contracts.schema import validate_graph_document
from vgar.graph.visualization import plot_graph_tracking


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot graph/context/resolver diagnostics with Matplotlib")
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, help="Optional PNG/SVG destination")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--debug-log", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--query", default="")
    parser.add_argument("--max-nodes", type=int, default=60)
    args = parser.parse_args()
    if not args.output and not args.show:
        parser.error("provide --show or --output")
    import matplotlib
    if not args.show:
        matplotlib.use("Agg")
    document = json.loads(args.graph.read_text(encoding="utf-8"))
    validate_graph_document(document)
    events = []
    if args.debug_log:
        for number, line in enumerate(args.debug_log.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"event": "invalid_log_line", "line": number})
    context = json.loads(args.context.read_text(encoding="utf-8")) if args.context else None
    figure = plot_graph_tracking(document, events=events, context=context, query=args.query, max_nodes=args.max_nodes)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.output, dpi=160)
        print(args.output)
    if args.show:
        import matplotlib.pyplot as plt
        plt.show()


if __name__ == "__main__":
    main()
