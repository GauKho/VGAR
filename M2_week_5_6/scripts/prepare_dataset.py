import argparse
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from m2_retrieval.dataset import prepare_dataset
from m2_retrieval.evidence import new_run, source_fingerprint, utc_now, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--revision")
    args = parser.parse_args()
    directory, record = new_run(ROOT / "results" / "dataset", "dataset_preparation")
    started = time.perf_counter()
    record["source"] = source_fingerprint(ROOT)
    try:
        manifest, metadata = prepare_dataset(ROOT, args.count, revision=args.revision)
        record.update(status="SUCCEEDED", manifest=str(manifest), dataset_revision=metadata["dataset_revision"],
                      raw_count=metadata["selection_audit"]["raw_count"], eligible_count=metadata["selection_audit"]["eligible_count"],
                      selected_count=len(metadata["tasks"]), exit_code=0)
        record.update(stdout=f"Manifest: {manifest}\nEligible={record['eligible_count']}; selected={record['selected_count']}\n", stderr="")
        print(f"Manifest: {manifest}\nEligible: {record['eligible_count']}; selected={record['selected_count']}")
    except Exception as exc:
        record.update(status="FAILED", error_class=type(exc).__name__, error=str(exc), exit_code=1)
        record.update(stdout="", stderr=str(exc))
        print(f"Preparation failed: {exc}", file=sys.stderr)
    record.update(complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started)
    write_json(directory / "result.json", record)
    print(f"Evidence: {directory / 'result.json'}")
    return record["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
