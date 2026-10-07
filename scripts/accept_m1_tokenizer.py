"""Reproduce standalone M1 retrieval acceptance with the approved local tokenizer."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vgar.contracts.context import ContextPayload
from vgar.graph.builder import PythonGraphBuilder
from vgar.source_scope import SourceScope
from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
from vgar.graph.task_overlay import TaskOverlayBuilder
from vgar.graph.token_counter import LocalTokenizerCounter


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_hashes(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in SourceScope.for_repository(root).python_files(root)}


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-manifest", type=Path, required=True)
    parser.add_argument("--graph-output", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    counter = LocalTokenizerCounter(args.tokenizer_manifest)
    import tokenizers
    manifest_path = args.tokenizer_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = Path(manifest["assets_directory"])
    if not assets.is_absolute():
        assets = manifest_path.parent / assets
    native = tokenizers.Tokenizer.from_file(str(assets / "tokenizer.json"))
    native.no_padding()
    native.no_truncation()
    samples = ("", "def f():\n    return 42\n", "đếm token 世界 🐻\r\n", "<|im_start|>user\n", "return 42\n" * 2000)
    sample_counts = []
    for text in samples:
        expected = len(native.encode(text, add_special_tokens=False).ids)
        assert counter(text) == expected
        sample_counts.append({"text_sha256": hashlib.sha256(text.encode()).hexdigest(), "token_count": expected})
    # A single candidate establishes exact-fit/one-token-short behavior using real tokens.
    with tempfile.TemporaryDirectory() as directory:
        tiny_root = Path(directory)
        (tiny_root / "unicode.py").write_bytes('def café():\r\n    return "đếm 世界 🐻"\r\n'.encode("utf-8"))
        tiny_graph = PythonGraphBuilder(repo_key="tokenizer-boundary", repository_revision="fixture",
                                        use_jedi=False).build(tiny_root)
        anchor = next(node for node in tiny_graph["nodes"] if node["type"] == "Function" and node["name"] == "café")
        raw = (tiny_root / "unicode.py").read_bytes()
        snippet = raw[anchor["range"]["start_byte"]:anchor["range"]["end_byte"]].decode("utf-8")
        cost = len(native.encode(snippet, add_special_tokens=False).ids)
        tiny_retriever = GraphContextRetriever(tiny_graph, tiny_root, count_tokens=counter,
            counter_label=counter.counter_label, config=RetrievalConfig(max_hops=0))
        fit = tiny_retriever.get_related_context([anchor["id"]], cost)
        short = tiny_retriever.get_related_context([anchor["id"]], cost - 1)
        assert len(fit.items) == 1 and fit.total_token_count == cost and not fit.truncated
        assert not short.items and short.total_token_count == 0 and short.truncated
        assert fit.items[0].snippet == snippet

    source_before = source_hashes(ROOT)
    shared_paths = ("src/vgar/contracts/schema.py", "src/vgar/contracts/context.py",
                    "src/vgar/contracts/graph.py", "src/vgar/contracts/error.py")
    shared_before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in shared_paths}
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT)]
    base_commit = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(git + ["status", "--porcelain"], text=True).strip())
    graph = PythonGraphBuilder(repo_key="GauKho/VGAR", repository_revision=f"{base_commit}-worktree-m1-tokenizer",
                               use_jedi=False).build(ROOT)
    write(args.graph_output, graph)
    graph_hash = hashlib.sha256(args.graph_output.read_bytes()).hexdigest()
    retriever = GraphContextRetriever(graph, ROOT, count_tokens=counter, counter_label=counter.counter_label)
    tasks = [
        ("builder-context", "src/vgar/graph/builder.py:93 has a nested scope bug",
         ["tests/test_graph_builder.py::GraphBuilderRegressionTests::test_nested_function_shadows_module_function"]),
        ("validator-context", "ContextItem path validation in src/vgar/contracts/context.py:36 fails",
         ["tests/test_context_contract.py::ContextPayloadContractTests::test_windows_drive_and_unc_paths_are_rejected_through_both_imports"]),
        ("empty-context", "missing.py:999", []),
    ]
    task_results = []
    for task_id, issue, failures in tasks:
        overlay = TaskOverlayBuilder(graph).build(task_id, issue, failures)
        result = retriever.retrieve([anchor.node_id for anchor in overlay.grounding.anchors], 8000,
                                    issue_text=issue, overlay=overlay)
        counts = [len(native.encode(item.snippet, add_special_tokens=False).ids) for item in result.context.items]
        assert counts == [item.token_count for item in result.context.items]
        assert result.context.total_token_count == sum(counts) <= 8000
        if task_id == "empty-context":
            assert not result.context.items and not result.context.truncated
        else:
            assert result.context.items
        output = asdict(result)
        output["context"] = result.context.model_dump(mode="json")
        output["tokenizer_provenance"] = counter.provenance
        ContextPayload.model_validate(output["context"])
        write(args.output_directory / f"{task_id}.json", output)
        task_results.append({"task_id": task_id, "artifact": f"{task_id}.json", "item_count": len(counts),
                             "candidate_count": len(result.candidates), "budget_tokens": 8000,
                             "total_token_count": sum(counts), "truncated": result.context.truncated})
    cli = subprocess.run([sys.executable, str(ROOT / "scripts/get_related_context.py"), str(args.graph_output), str(ROOT),
                          "--budget-tokens", "8000", "--tokenizer-manifest", str(manifest_path), "--explain",
                          "--task-id", tasks[0][0], "--issue-text", tasks[0][1], "--failing-test", tasks[0][2][0]],
                         check=True, capture_output=True, text=True, encoding="utf-8")
    cli_output = json.loads(cli.stdout)
    assert cli_output == json.loads((args.output_directory / "builder-context.json").read_text(encoding="utf-8"))
    write(args.output_directory / "cli_context.json", cli_output)
    assert source_hashes(ROOT) == source_before
    assert hashlib.sha256(args.graph_output.read_bytes()).hexdigest() == graph_hash
    assert shared_before == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in shared_paths}
    write(args.output_directory / "manifest.json", {
        "date": "2026-10-03", "base_commit": base_commit, "working_tree_dirty": dirty,
        "graph_artifact": str(args.graph_output.resolve()), "graph_version": graph["graph_version"],
        "graph_json_sha256": graph_hash, "statistics": graph["statistics"], "use_jedi": False,
        "tokenizer_provenance": counter.provenance, "snippet_only_budget": True,
        "native_count_comparison": True, "sample_counts": sample_counts,
        "boundary": {"exact_fit_tokens": cost, "one_token_short_budget": cost - 1, "checks_passed": True},
        "tasks": task_results, "cli_pass": True,
        "source_hashes_before": source_before, "source_hashes_after": source_hashes(ROOT),
        "source_unchanged_during_acceptance": True, "base_graph_unchanged_during_acceptance": True,
        "shared_contract_hashes": shared_before,
        "limitations": ["Synthetic inputs; no real failing-test execution claimed", "No retrieval quality/latency benchmark",
                        "Standalone M1; M3 model revision/prompt allocation/integration remain separate"],
    })
    print(json.dumps({"tasks": task_results, "boundary_tokens": cost, "native_count_comparison": True,
                      "cli_pass": True, "statistics": graph["statistics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
