"""Synthetic prompt inputs/config only; serves the real renderer, with no provider/model."""
import argparse
from pathlib import Path

from vgar.mcp.audit import AuditLogger
from vgar.mcp.proposal.prompts import PromptRenderer
from vgar.mcp.servers import graph_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=False)
    graph_server._audit_logger = AuditLogger(root / "audit.jsonl")
    graph_server.prompt_renderer = PromptRenderer(secret_values=("opaque-synthetic-secret-value",))
    graph_server.main()


if __name__ == "__main__":
    main()
