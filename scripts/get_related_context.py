"""M1 CLI: anchors -> source-verified ContextPayload, independent of MCP."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vgar.contracts.error import GraphError
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
from vgar.graph.task_overlay import TaskOverlayBuilder
from vgar.graph.token_counter import LocalTokenizerCounter


def main() -> int:
    # Windows redirected stdout can default to cp1252; snippets are UTF-8 JSON.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Retrieve M1 graph context under an explicit snippet budget.")
    parser.add_argument("graph", type=Path)
    parser.add_argument("repository_root", type=Path)
    parser.add_argument("--budget-tokens", type=int, required=True)
    parser.add_argument("--anchor-id", action="append", default=[])
    issue = parser.add_mutually_exclusive_group()
    issue.add_argument("--issue-text")
    issue.add_argument("--issue-file", type=Path)
    parser.add_argument("--task-id", default="m1-context-cli")
    parser.add_argument("--failing-test", action="append", default=[])
    counter = parser.add_mutually_exclusive_group(required=True)
    counter.add_argument("--demo-counter", action="store_true",
                         help="Whitespace units for smoke only; NOT model tokens.")
    counter.add_argument("--tokenizer-id")
    counter.add_argument("--tokenizer-manifest", type=Path,
                         help="Local M1 tokenizer-only manifest with revision and verified hashes.")
    parser.add_argument("--tokenizer-revision")
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--history-file", type=Path, help="JSON node-ID/path -> nonnegative change counts.")
    parser.add_argument("--history-label", help="Source/window of supplied historical counts.")
    parser.add_argument("--explain", action="store_true", help="Include M1 diagnostics outside shared payload.")
    args = parser.parse_args()
    if args.tokenizer_id and not args.tokenizer_revision:
        parser.error("--tokenizer-id requires an explicit --tokenizer-revision")
    if args.tokenizer_revision and not args.tokenizer_id:
        parser.error("--tokenizer-revision is only used with --tokenizer-id; manifests already pin revision")
    if args.history_file and not args.history_label:
        parser.error("--history-file requires --history-label")
    tokenizer_provenance = None
    if args.demo_counter:
        count_tokens = lambda text: len(re.findall(r"\S+", text))
        counter_label = "demo-whitespace-units:not-model-tokens"
        print(f"Counter: {counter_label}; budget applies to snippet units only", file=sys.stderr)
    elif args.tokenizer_manifest:
        try:
            count_tokens = LocalTokenizerCounter(args.tokenizer_manifest)
        except (OSError, ValueError, RuntimeError) as error:
            parser.error(f"Cannot load verified local tokenizer: {error}")
        counter_label = count_tokens.counter_label
        tokenizer_provenance = count_tokens.provenance
    else:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                args.tokenizer_id, revision=args.tokenizer_revision, local_files_only=True,
            )
        except (ImportError, OSError) as error:
            parser.error(f"Tokenizer must be provisioned locally before retrieval: {error}")
        count_tokens = lambda text: len(tokenizer.encode(text, add_special_tokens=False))
        counter_label = f"huggingface:{args.tokenizer_id}@{args.tokenizer_revision}:no-special-tokens"
    document = json.loads(args.graph.read_text(encoding="utf-8-sig"))
    text = args.issue_file.read_text(encoding="utf-8-sig") if args.issue_file else (args.issue_text or "")
    overlay = None
    if text or args.failing_test:
        overlay = TaskOverlayBuilder(document).build(args.task_id, text, args.failing_test)
    anchors = args.anchor_id or ([anchor.node_id for anchor in overlay.grounding.anchors] if overlay else [])
    history = json.loads(args.history_file.read_text(encoding="utf-8-sig")) if args.history_file else None
    try:
        retriever = GraphContextRetriever(
            document, args.repository_root, count_tokens=count_tokens, counter_label=counter_label,
            config=RetrievalConfig(max_hops=args.max_hops, max_candidates=args.max_candidates),
            change_counts=history, history_label=args.history_label,
        )
        result = retriever.retrieve(anchors, args.budget_tokens, issue_text=text, overlay=overlay)
    except GraphError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 1
    output = result.context.model_dump(mode="json")
    if args.explain:
        output = asdict(result)
        output["context"] = result.context.model_dump(mode="json")
        if tokenizer_provenance is not None:
            output["tokenizer_provenance"] = tokenizer_provenance
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
