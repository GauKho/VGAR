"""Reduced real-source diagnostic, NOT benchmark output or an alternative corpus."""
import argparse
import cProfile
import gc
import json
import pstats
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from vgar.evaluation.retrieval.evidence import new_run, write_json
from vgar.evaluation.retrieval.worker import peak_rss_bytes
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.retrieval import GraphContextRetriever
from vgar.graph.task_overlay import TaskOverlayBuilder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=30)
    args = parser.parse_args()
    run, record = new_run(Path(__file__).parent / "preparation-profile", "reduced-preparation-diagnostic")
    record.update(benchmark=False, sample_files=args.files, phases=[])
    started = time.perf_counter()
    try:
        tree = None
        for marker in (ROOT / "data/repositories/trees/rebuilt").glob("*/.vgar_tree.json"):
            meta = json.loads(marker.read_text(encoding="utf-8"))
            if meta.get("repo") == "sympy/sympy":
                tree = marker.parent
                break
        if tree is None:
            raise ValueError("Missing preserved Sympy tree")
        class SampleBuilder(PythonGraphBuilder):
            def _discover_python_files(self, root):
                # Diagnostic subclass only. Production corpus/filter stays unchanged.
                return super()._discover_python_files(root)[:args.files]
        builder = SampleBuilder(repo_key="sympy-profile", repository_revision=meta["commit"], use_jedi=False)
        document = builder.build(tree)
        record.update(tree=str(tree), nodes=len(document["nodes"]), edges=len(document["edges"]))
        for name, factory in [
            ("TaskOverlayBuilder", lambda: TaskOverlayBuilder(document)),
            ("GraphContextRetriever", lambda: GraphContextRetriever(document, tree, count_tokens=lambda s: len(s), counter_label="diagnostic-char")),
            ("GraphContextRetrieverOwned", lambda: GraphContextRetriever(document, tree, count_tokens=lambda s: len(s), counter_label="diagnostic-char", _take_ownership=True)),
        ]:
            profiler = cProfile.Profile()
            start = time.perf_counter()
            profiler.enable()
            instance = factory()
            profiler.disable()
            stats = pstats.Stats(profiler)
            hottest = sorted(stats.stats.items(), key=lambda pair: pair[1][3], reverse=True)[:12]
            record["phases"].append({"name": name, "seconds": time.perf_counter() - start,
                "peak_rss_bytes": peak_rss_bytes(), "calls": stats.total_calls,
                "hottest": [{"function": str(key), "calls": value[1], "self_seconds": value[2], "cumulative_seconds": value[3]} for key, value in hottest]})
            write_json(run / "result.json", record)
            del instance
            gc.collect()
        record.update(status="PASS", exit_code=0)
    except Exception as exc:
        record.update(status="ERROR", exit_code=1, error=str(exc), traceback=traceback.format_exc())
    record.update(complete=True, duration_seconds=time.perf_counter() - started)
    write_json(run / "result.json", record)
    print(json.dumps({"evidence": str(run / "result.json"), "status": record["status"], "nodes": record.get("nodes"), "phases": record.get("phases")}, ensure_ascii=False))
    return record["exit_code"]

if __name__ == "__main__":
    raise SystemExit(main())
