from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.scip_resolver import ScipConfig
from vgar.graph.lsp_resolver import LspConfig
from vgar.observability.graph_trace import GraphTrace


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a JSON document using the frozen VGAR graph contract."
    )
    parser.add_argument("repository", help="Python repository root")
    parser.add_argument("output", help="Destination graph JSON")
    parser.add_argument("--repo-key", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--resolver", choices=("static", "scip", "lsp", "scip-lsp"), default="static")
    parser.add_argument("--scip-entry", type=Path, help="scip-python index.js from a pinned local installation")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--scip-bundle", type=Path, help="Previously generated manifest.json and index.scip")
    parser.add_argument("--scip-timeout", type=float, default=120)
    parser.add_argument("--scip-environment", type=Path, help="Package inventory JSON for the target Python environment")
    parser.add_argument("--scip-native-config", action="store_true", help="Disable isolated import-root configuration")
    parser.add_argument("--scip-import-root", action="append", help="Repository-relative import root; defaults to existing src/lib")
    parser.add_argument("--scip-target-only", help="Optional directory subset; remaining graph uses static fallback")
    parser.add_argument("--scip-python", type=Path, help="Python interpreter for SCIP; provide matching --scip-environment")
    parser.add_argument("--strict-resolver", action="store_true", help="Fail instead of static fallback")
    parser.add_argument("--lsp-entry", type=Path, help="Pinned Pyright langserver.index.js")
    parser.add_argument("--lsp-timeout", type=float, default=30, help="Total LSP query time budget")
    parser.add_argument("--lsp-request-timeout", type=float, default=5)
    parser.add_argument("--lsp-max-requests", type=int, default=200)
    parser.add_argument("--lsp-python", type=Path, help="Python interpreter used for LSP import resolution")
    parser.add_argument("--lsp-import-root", action="append", help="Repository-relative import root")
    parser.add_argument("--debug-log", type=Path)
    args = parser.parse_args()

    scip = None
    if args.resolver in {"scip", "scip-lsp"}:
        runtime = Path(__file__).resolve().parents[1] / "artifacts/m1/w7-w8/scip-runtime/node_modules/@sourcegraph/scip-python/index.js"
        entry = (args.scip_entry or runtime).resolve()
        shim = Path(__file__).with_name("scip_windows_compat.cjs").resolve()
        node = shutil.which(args.node) or args.node
        scip = ScipConfig(command=(str(Path(node).resolve()), "-r", str(shim), str(entry)),
                          bundle=args.scip_bundle, timeout_seconds=args.scip_timeout, strict=args.strict_resolver,
                          environment_file=args.scip_environment, configure_imports=not args.scip_native_config,
                          import_roots=tuple(args.scip_import_root or ("src", "lib")), target_only=args.scip_target_only,
                          python_executable=args.scip_python)

    lsp = None
    if args.resolver in {"lsp", "scip-lsp"}:
        runtime = Path(__file__).resolve().parents[1] / "artifacts/m1/w5-w6/lsp-runtime/node_modules/pyright/langserver.index.js"
        entry = (args.lsp_entry or runtime).resolve()
        node = shutil.which(args.node) or args.node
        lsp = LspConfig(command=(str(Path(node).resolve()), str(entry), "--stdio"),
                        total_timeout=args.lsp_timeout, request_timeout=args.lsp_request_timeout,
                        max_requests=args.lsp_max_requests, python_executable=args.lsp_python,
                        import_roots=tuple(args.lsp_import_root or ("src", "lib")), strict=args.strict_resolver)

    builder = PythonGraphBuilder(
        repo_key=args.repo_key,
        repository_revision=args.revision,
        scip=scip,
        lsp=lsp,
        trace=GraphTrace(args.debug_log),
    )
    document = builder.build(args.repository)
    resolver = document["statistics"]["resolver"]
    if resolver["status"] == "fallback":
        print(f"WARNING: {resolver['requested']} -> static fallback: {resolver['reason']}", file=sys.stderr)
    if resolver.get("lsp", {}).get("status") in {"fallback", "partial"}:
        print(f"WARNING: LSP fallback: {resolver['lsp']['reason']}", file=sys.stderr)

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
