"""VGAR command line: settings and graph indexing.

    vgar doctor                      # resolved settings
    vgar index REPO --db graph.db    # build the graph snapshot the MCP graph server reads

The MCP servers (graph, execution, repository) run as their own processes;
attach them to a coding agent (Claude Code, OpenCode) through its MCP config.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from vgar.config.settings import get_settings
from vgar.graph.indexing import index_repo


# --------------------------------------------------------------------- commands
async def cmd_doctor(args: argparse.Namespace) -> int:
    s = get_settings()
    print(json.dumps({
        "graph": {k: str(v) for k, v in vars(s.graph).items()}, "audit_log": str(s.audit_log),
    }, indent=2, ensure_ascii=False))
    return 0


async def cmd_index(args: argparse.Namespace) -> int:
    print(f"{index_repo(Path(args.repo).resolve(), Path(args.db))} nodes -> {args.db}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vgar", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="print resolved settings").set_defaults(fn=cmd_doctor)

    ix = sub.add_parser("index", help="build graph snapshot")
    ix.add_argument("repo")
    ix.add_argument("--db", default="artifacts/graph.db")
    ix.set_defaults(fn=cmd_index)

    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
