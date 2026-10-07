"""Append-only handoff evidence from completed measurements, no task reruns."""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from vgar.evaluation.retrieval.evidence import new_run, sha256, utc_now, write_json


def stats(values):
    if not values:
        return dict(n=0, mean=None, median=None, p95=None, maximum=None)
    ordered = sorted(values)
    return dict(n=len(values), mean=statistics.fmean(values), median=statistics.median(values),
                p95=ordered[math.ceil(.95 * len(ordered)) - 1], maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph-run', required=True, type=Path)
    parser.add_argument('--comparison', required=True, type=Path)
    args = parser.parse_args()
    directory, record = new_run(ROOT / 'artifacts/fixes/w3-w6/benchmark-handoff', 'terminal-benchmark-analysis')
    started = time.perf_counter()
    try:
        raw_graph = (args.graph_run / 'result.json').read_bytes()
        raw_compare = (args.comparison / 'result.json').read_bytes()
        graph, compared = json.loads(raw_graph), json.loads(raw_compare)
        assert graph['complete'] and compared['complete']
        assert compared['graph_run_hash'] == sha256(raw_graph)
        assert graph['config']['graph']['use_jedi'] is False
        assert graph['config']['budget_tokens'] == 8000
        assert len(graph['task_results']) == 25
        successes, failures = [], []
        for summary in graph['task_results']:
            path = args.graph_run / 'tasks' / (summary['instance_id'] + '.json')
            raw = path.read_bytes()
            assert sha256(raw) == summary['artifact_hash']
            task = json.loads(raw)
            assert task['instance_id'] == summary['instance_id'] and task['status'] == summary['status']
            if summary['status'] == 'SUCCEEDED':
                successes.append(dict(instance_id=summary['instance_id'], duration_seconds=task['duration_seconds'],
                    peak_rss_bytes=task['peak_rss_bytes'], graph_cached=summary['graph_cached'],
                    graph_build_seconds=summary['graph_build_seconds'],
                    observed_build_stage_seconds=sum(stage['duration_seconds'] for stage in task['stages']
                                                     if stage['phase'] == 'BUILD_GRAPH'),
                    graph_metrics=task['arms']['graph']['metrics'],
                    stages=task['stages'], task_path=str(path), task_sha256=sha256(raw)))
            else:
                failures.append(dict(task_path=str(path), task_sha256=sha256(raw), evidence=task))
        record.update(status='PASS', exit_code=0, complete=True, inference='NOT_RUN',
            graph_run_path=str(args.graph_run), graph_run_sha256=sha256(raw_graph),
            comparison_path=str(args.comparison), comparison_sha256=sha256(raw_compare),
            source_fingerprint=graph['source']['digest'], config=graph['config'],
            attempted=25, succeeded=len(successes), failed=len(failures),
            run_wall_seconds=graph['duration_seconds'], paired_tasks=compared['paired_tasks'],
            benchmark_status=graph['status'], comparison_status=compared['status'],
            paired25_gate_met=len(successes) == 25 and compared['paired_tasks'] == 25,
            conditional_comparison=compared, successes=successes, failures=failures,
            success_latency_seconds=stats([task['duration_seconds'] for task in successes]),
            all_attempt_latency_seconds=stats([task['duration_seconds'] for task in graph['task_results']]),
            success_graph_build_seconds=stats([task['graph_build_seconds'] for task in successes]),
            success_observed_build_stage_seconds=stats([task['observed_build_stage_seconds'] for task in successes]),
            build_time_policy='graph_build_seconds may be historical cached build metadata; observed stage includes current cache loading/validation.',
            success_peak_rss_bytes=stats([task['peak_rss_bytes'] for task in successes]),
            max_observed_rss_bytes=max(task['peak_rss_bytes'] for task in graph['task_results']),
            cache_hits=sum(task['graph_cached'] for task in successes),
            latency_policy='Observed single-worker wall times; mixed cache states, not a controlled model/CPU benchmark.',
            api_inference_usd=0, environment_readiness='EXCLUDED_BY_USER_NOT_RUN',
            owner_signoffs='PENDING; never assigned by Codex')
    except Exception as exc:
        import traceback
        record.update(status='ERROR', complete=True, exit_code=1, error_class=type(exc).__name__,
                      error=str(exc), traceback=traceback.format_exc())
    finally:
        record.update(ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
        write_json(directory / 'result.json', record)
    fields = ('status', 'attempted', 'succeeded', 'failed', 'paired_tasks', 'run_wall_seconds',
              'success_latency_seconds', 'success_observed_build_stage_seconds', 'max_observed_rss_bytes', 'cache_hits')
    print(json.dumps(dict(evidence=str(directory / 'result.json'), **{name: record.get(name) for name in fields}), ensure_ascii=False))
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
