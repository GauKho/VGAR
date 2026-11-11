"""Trusted static-analysis worker. JSON IPC only; no authority, grants or DB writes."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from vgar.graph.incremental import IncrementalGraphBuilder
from vgar.graph.storage_capabilities import canonical_bytes


def main():
    builder, fingerprint, pending = None, None, None
    for line in sys.stdin.buffer:
        try:
            request = json.loads(line)
            if request["action"] == "ack":
                if pending != request["job_id"]:
                    raise ValueError("ACK does not match pending job")
                pending = None
                reply = {"job_id": request["job_id"], "status": "ACK"}
            else:
                if pending is not None:
                    raise ValueError("Previous worker result not acknowledged")
                job_id = request["job_id"]
                stage = Path(request["stage"])
                options = request["options"]
                started = time.monotonic()
                cold = builder is None or fingerprint != request["fingerprint"]
                if cold:
                    builder = IncrementalGraphBuilder(options["repo_key"], options["repository_revision"],
                                                      source_roots=tuple(options["source_roots"]))
                    document = builder.build(stage / "source")
                    summary = {"changed_files": [], "added_files": sorted(builder._digests), "deleted_files": [],
                               "cache_hits": 0, "total_files": len(builder._digests),
                               "affected_node_count": len(document["nodes"])}
                else:
                    document, report = builder.update(stage / "source")
                    summary = asdict(report)
                summary["worker_elapsed_ms"] = round((time.monotonic()-started)*1000)
                (stage / "document.json").write_bytes(canonical_bytes(document))
                (stage / "summary.json").write_bytes(canonical_bytes(summary))
                reply = {"job_id": job_id, "status": "READY", "fingerprint": request["fingerprint"],
                         "worker_instance": sys.argv[1],
                         "mode": "COLD_BUILD" if cold else "WARM_UPDATE", "worker_pid": os.getpid(),
                         "document_hash": "sha256:" + hashlib.sha256((stage/"document.json").read_bytes()).hexdigest(),
                         "summary_hash": "sha256:" + hashlib.sha256((stage/"summary.json").read_bytes()).hexdigest()}
                fingerprint, pending = request["fingerprint"], job_id
        except Exception as exc:  # noqa: BLE001 - IPC returns safe type, never raw source/error text
            reply = {"status": "ERROR", "error_type": type(exc).__name__}
            builder, fingerprint, pending = None, None, None
        sys.stdout.buffer.write(canonical_bytes(reply) + b"\n")
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
