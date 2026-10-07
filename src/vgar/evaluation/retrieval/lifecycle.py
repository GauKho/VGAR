"""Parent-owned task deadlines and immutable resume forks for retrieval evaluation."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from vgar.repair.test_runner import _WindowsJob, _kill_tree
from .evidence import sha256, utc_now, write_json
from .worker import peak_rss_bytes

MAX_WORKER_OUTPUT = 8 * 1024 * 1024


def _tree_rss(process, job) -> int:
    """Observed resident set, including the real child of Windows venv launchers."""
    if os.name != "nt":
        return peak_rss_bytes(process)
    import ctypes
    from ctypes import wintypes
    size = 8 + 512 * ctypes.sizeof(ctypes.c_size_t)
    buffer = ctypes.create_string_buffer(size)
    kernel = job.kernel
    kernel.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    if not kernel.QueryInformationJobObject(job.handle, 3, buffer, size, None):
        raise OSError(ctypes.get_last_error(), "Cannot enumerate worker process tree")
    assigned, count = (wintypes.DWORD * 2).from_buffer(buffer)
    if assigned > count:
        raise OSError("Worker process tree exceeds RSS sampling capacity")
    ids = (ctypes.c_size_t * count).from_buffer(buffer, 8)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = ctypes.c_void_p
    rss = 0
    # Layout prefix of PROCESS_MEMORY_COUNTERS up to current WorkingSetSize.
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    for pid in ids:
        handle = kernel.OpenProcess(0x410, False, pid)
        if not handle:
            continue  # exited between enumeration and sampling
        try:
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                rss += counters.WorkingSetSize
        finally:
            kernel.CloseHandle(handle)
    return rss


def run_worker(request: dict, directory: Path, timeout_seconds: float, *, worker_command=None) -> dict:
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError("Worker timeout must be positive and finite")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    request_path = directory / "request.json"
    write_json(request_path, request)
    command = list(worker_command or [sys.executable, "-B", "-m", "vgar.evaluation.retrieval.worker"])
    command += [str(request_path), str(directory)]
    record = {"instance_id": request["row"]["instance_id"], "status": "RUNNING", "complete": False,
              "command_argv": command, "cwd": str(Path.cwd()), "interpreter": sys.executable,
              "timeout_seconds": timeout_seconds, "started_utc": utc_now(), "phase": "START_WORKER"}
    write_json(directory / "result.json", record)
    environment = os.environ.copy()
    environment.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false")
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
    # Workers use public source archives/offline tokenizer assets, not credentials.
    for key in list(environment):
        name = key.upper()
        if (name == "TOKEN" or name.endswith("_TOKEN")
                or any(part in name for part in ("API_KEY", "PASSWORD", "SECRET", "ACCESS_TOKEN"))):
            environment.pop(key, None)
    started = time.perf_counter()
    process = job = None
    error = None
    interrupted = False
    samples, peak, next_sample = [], 0, 0.0
    try:
        with (directory / "stdout.log").open("wb") as out, (directory / "stderr.log").open("wb") as err:
            process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err, shell=False,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                                       start_new_session=os.name != "nt")
            if os.name == "nt":
                try:
                    job = _WindowsJob(process)
                except OSError:
                    process.kill()
                    process.wait()
                    raise
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                if elapsed >= next_sample:
                    try:
                        rss = _tree_rss(process, job)
                    except OSError as exc:
                        record["rss_warning"] = str(exc)
                    else:
                        peak = max(peak, rss)
                        samples.append({"elapsed_seconds": elapsed, "peak_rss_bytes": rss})
                    next_sample = elapsed + 0.5
                    try:
                        current = json.loads((directory / "telemetry.json").read_text(encoding="utf-8"))
                        record.update(current)
                    except (OSError, ValueError):
                        pass
                    record["peak_rss_bytes"] = max(peak, record.get("peak_rss_bytes", 0))
                    write_json(directory / "result.json", record)
                if time.perf_counter() - started >= timeout_seconds:
                    raise TimeoutError("Retrieval task exceeded its deadline")
                if any((directory / name).stat().st_size > MAX_WORKER_OUTPUT for name in ("stdout.log", "stderr.log")):
                    raise RuntimeError("Worker output limit exceeded; full captured files retained")
                time.sleep(0.05)
            process.wait()
    except (Exception, KeyboardInterrupt) as exc:
        error = {"error_class": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}
        interrupted = isinstance(exc, KeyboardInterrupt)
    finally:
        try:
            if process is not None:
                if process.poll() is None:
                    _kill_tree(process, job)
                # Also clean descendants when the worker has already exited.
                if job is not None:
                    job.terminate()
                elif os.name != "nt":
                    import signal
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except Exception as exc:
            record["cleanup_error"] = traceback.format_exc()
            error = error or {"error_class": type(exc).__name__, "error": str(exc), "traceback": record["cleanup_error"]}
        finally:
            if job is not None:
                job.close()
        telemetry = {}
        try:
            telemetry = json.loads((directory / "telemetry.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        worker_result = None
        try:
            worker_result = json.loads((directory / "worker-result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        record.update(telemetry)
        if error is None and worker_result is not None:
            if (worker_result.get("instance_id") != request["row"]["instance_id"]
                    or worker_result.get("status") not in {"SUCCEEDED", "FAILED"}
                    or not worker_result.get("complete")
                    or (worker_result["status"] == "SUCCEEDED" and process.returncode != 0)):
                error = {"error_class": "WorkerProcessError", "error": "Invalid worker result/exit binding", "traceback": ""}
            else:
                record.update(worker_result)
        elif error is None:
            error = {"error_class": "WorkerProcessError", "error": "Worker exited without terminal JSON", "traceback": ""}
        if error is not None:
            record.update(error, status="ERROR")
        record.update(worker_exit_code=process.returncode if process is not None else None,
                      complete=True, ended_utc=utc_now(), duration_seconds=time.perf_counter() - started,
                      rss_samples=samples, peak_rss_bytes=max(peak, record.get("peak_rss_bytes", 0)),
                      rss_measurement="max(worker-reported peak RSS, parent-observed tree RSS at 0.5s intervals); not GPU/virtual memory")
        for name in ("stdout", "stderr"):
            path = directory / f"{name}.log"
            if path.exists():
                with path.open("rb") as stream:
                    record[name] = stream.read(MAX_WORKER_OUTPUT).decode("utf-8", errors="replace")
                if path.stat().st_size > MAX_WORKER_OUTPUT:
                    record.update(status="ERROR", output_truncated=True, error_class="OutputLimitError",
                                  error="Embedded output capped; full captured log files retained")
            else:
                record[name] = ""
        write_json(directory / "result.json", record)
    if interrupted:
        raise KeyboardInterrupt()
    return record


def resume_successes(prior: Path, destination: Path, identity: dict) -> dict[str, dict]:
    """Copy verified successes into a NEW run; failures get fresh attempts there.

    No old result/artifact is modified, including runs interrupted by a hard kill.
    Legacy runs without an identity cannot safely resume and are rejected.
    """
    prior, destination = Path(prior).resolve(), Path(destination).resolve()
    record = json.loads((prior / "result.json").read_text(encoding="utf-8"))
    if record.get("kind") != "retrieval_graph" or record.get("resume_identity") != identity:
        raise ValueError("Cannot resume: identity differs (manifest/config/code/source root/tokenizer/F2P)")
    successes, seen = {}, set()
    for summary in record["task_results"]:
        iid = summary["instance_id"]
        import re
        if not isinstance(iid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", iid) or iid in seen:
            raise ValueError("Cannot resume duplicate/invalid task IDs")
        seen.add(iid)
        if summary["status"] != "SUCCEEDED":
            continue
        artifact = prior / "tasks" / f"{iid}.json"
        raw = artifact.read_bytes()
        if sha256(raw) != summary.get("artifact_hash"):
            raise ValueError("Cannot resume: success artifact hash mismatch")
        value = json.loads(raw)
        if (value.get("instance_id") != iid
                or value.get("status") != "SUCCEEDED"):
            raise ValueError("Cannot resume: success artifact hash/status mismatch")
        target = destination / "tasks" / artifact.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError("Resume destination must not contain existing task artifacts")
        shutil.copyfile(artifact, target)
        successes[iid] = dict(summary, reused_from_run=str(prior))
    return successes
