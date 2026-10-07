"""One task per subprocess: phases, full errors and RSS without loading an LLM."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path

from .evidence import sha256, utc_now, write_json


def peak_rss_bytes(process=None) -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        *[(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                           "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        handle = int(process._handle) if process is not None else kernel.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error(), "Cannot measure process RSS")
        return counters.PeakWorkingSetSize
    if process is not None:
        # Linux VmHWM is the peak resident set, not virtual allocation or GPU RAM.
        for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
        raise OSError("Process peak RSS is not available on this platform")
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


class StageRecorder:
    def __init__(self, directory: Path):
        self.path = directory / "telemetry.json"
        self.value = {"phase": "SETUP", "stages": [], "peak_rss_bytes": peak_rss_bytes()}
        write_json(self.path, self.value)

    @contextmanager
    def step(self, phase):
        self.value.update(phase=phase, peak_rss_bytes=peak_rss_bytes())
        write_json(self.path, self.value)
        started = time.perf_counter()
        try:
            yield
        finally:
            self.value["stages"].append({"phase": phase, "duration_seconds": time.perf_counter() - started,
                                         "peak_rss_bytes": peak_rss_bytes()})
            self.value["peak_rss_bytes"] = peak_rss_bytes()
            write_json(self.path, self.value)


def run_task(request: dict, stages: StageRecorder) -> dict:
    from vgar.graph.retrieval import GraphContextRetriever, RetrievalConfig
    from vgar.graph.task_overlay import TaskOverlayBuilder
    from .dataset import read_repository_sources
    from .graph_arm import ARMS, evaluate_graph_task, extract_python_tree
    from .graph_cache import load_or_build_graph
    from .scoring import CorpusIndex, FALLBACK_COUNTER_LABEL, bytes_div4_counter, make_include

    root, row, config = Path(request["root"]), request["row"], request["config"]
    with stages.step("TOKENIZER"):
        if request.get("tokenizer_manifest"):
            from vgar.graph.token_counter import LocalTokenizerCounter
            counter = LocalTokenizerCounter(request["tokenizer_manifest"])
            label = counter.counter_label
        else:
            counter, label = bytes_div4_counter, FALLBACK_COUNTER_LABEL
        if label != config["counter_label"] or sha256(row["problem_statement"]) != row["query_hash"]:
            raise ValueError("Counter/query differs from pinned request")
    with stages.step("LOAD_SOURCE"):
        sources, provenance = read_repository_sources(row, root / "data/repositories", network=not request["offline"])
    tree = root / "data/repositories/trees" / f"{row['repo'].replace('/', '__')}-{row['base_commit']}"
    with stages.step("EXTRACT_TREE"):
        if request.get("rebuild_trees", False):
            # Explicit recovery from newline-transformed/tampered legacy caches.
            # Preserve every prior tree; archive verification happened in LOAD_SOURCE.
            # Short namespace avoids Windows MAX_PATH expansion from repo+SHA.
            tree = tree.parent / "rebuilt" / uuid.uuid4().hex[:12]
        tree_meta = extract_python_tree(provenance["cache_path"], row["repo"], row["base_commit"], tree)
    with stages.step("BUILD_GRAPH"):
        document, graph_meta = load_or_build_graph(root, row, tree, use_jedi=config["graph"]["use_jedi"],
                                                    rebuild=request["rebuild_graphs"], builder_hash=config["graph"]["builder_hash"])
    with stages.step("PREPARE_RETRIEVAL"):
        corpus = CorpusIndex(sources)
        overlays = TaskOverlayBuilder(document)
        retrieval = config["retrieval"]
        retriever = GraphContextRetriever(document, tree, count_tokens=counter, counter_label=label,
                    config=RetrievalConfig(max_hops=retrieval["max_hops"], max_candidates=retrieval["max_candidates"]))
        include = make_include(corpus)
    outputs = {}
    for arm, uses_f2p in ARMS.items():
        started = time.perf_counter()
        with stages.step("GROUND"):
            overlay = overlays.build(f"{row['instance_id']}:{arm}", row["problem_statement"],
                                     request["failing_tests"] if uses_f2p else None)
            anchors = [{"node_id": a.node_id, "score": a.score, "symbol": retriever.nodes[a.node_id]["qualified_name"],
                        "type": retriever.nodes[a.node_id]["type"], "path": retriever.nodes[a.node_id]["path"]}
                       for a in overlay.grounding.anchors]
        with stages.step("RETRIEVE"):
            retrieved = retriever.retrieve([a["node_id"] for a in anchors], config["budget_tokens"],
                                            issue_text=row["problem_statement"], overlay=overlay, include=include)
            reasons = {}
            for omission in retrieved.omissions:
                reasons[omission["reason"]] = reasons.get(omission["reason"], 0) + 1
            outputs[arm] = {"candidates": retrieved.candidates, "anchors": anchors, "seconds": time.perf_counter() - started,
                           "diagnostics": {"m1_native_total_tokens": retrieved.context.total_token_count,
                               "m1_native_items": len(retrieved.context.items), "m1_native_truncated": retrieved.context.truncated,
                               "traversal_limited": retrieved.traversal_limited, "unavailable_features": retrieved.unavailable_features,
                               "omissions": reasons, "retrieval_config": retrieved.config}}
    # Gold is opened only AFTER issue-only/oracle ranking; never passed to grounding.
    with stages.step("SCORE"):
        patch_path = (root / row["gold_patch_path"]).resolve()
        if not patch_path.is_relative_to(root / "data/gold"):
            raise ValueError("Gold patch path outside data/gold")
        patch = patch_path.read_text(encoding="utf-8")
        if sha256(patch) != row["patch_hash"]:
            raise ValueError("Manifest patch hash mismatch")
        result = evaluate_graph_task(dict(row, patch=patch), sources, corpus, retriever.nodes, outputs,
                                    budget_tokens=config["budget_tokens"], counter=counter, counter_label=label)
        result.update(graph=graph_meta, source_tree={k: tree_meta[k] for k in ("python_file_count", "tree_hash")},
                      source_provenance=provenance, fail_to_pass_count=len(request["failing_tests"]), inference="NOT_RUN")
        result["source_tree"]["path"] = str(tree.resolve())
    return result


def main(argv=None) -> int:
    request_path, directory = map(Path, argv if argv is not None else sys.argv[1:])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    started = time.perf_counter()
    stages = StageRecorder(directory)
    try:
        result = run_task(request, stages)
        status = 0
    except (Exception, KeyboardInterrupt) as exc:
        result = {"instance_id": request["row"]["instance_id"], "status": "FAILED",
                  "error_class": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}
        status = 1
    with stages.step("WRITE"):
        result.update(stages.value, complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        # Do not hide the failing phase behind the terminal WRITE operation.
        if status:
            result["phase"] = stages.value["stages"][-1]["phase"] if stages.value["stages"] else "SETUP"
        write_json(directory / "worker-result.json", result)
    result["stages"] = stages.value["stages"]
    result["peak_rss_bytes"] = stages.value["peak_rss_bytes"]
    write_json(directory / "worker-result.json", result)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
