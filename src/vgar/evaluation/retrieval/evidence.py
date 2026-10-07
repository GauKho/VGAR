"""Durable JSON evidence; artifacts are append-only runs, never previous results."""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers/antivirus can briefly deny delete sharing even for an
        # atomic rename. Retry this specific error, never unlink the old artifact.
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.01)
    finally:
        temporary.unlink(missing_ok=True)


def source_fingerprint(root):
    root = Path(root).resolve()
    from vgar.source_scope import SourceScope
    paths = [root / name for name in ("pyproject.toml", "uv.lock", "requirements.txt", "requirements-dev.txt")]
    for name in ("src", "scripts", "tests", "config", "configs"):
        directory = root / name
        if directory.is_dir():
            paths.extend(path for _, path in SourceScope().files(directory))
    paths = sorted(set(paths))
    values = {p.relative_to(root).as_posix(): sha256(p.read_bytes()) for p in paths if p.is_file()}
    return {"files": values, "digest": sha256(json.dumps(values, sort_keys=True))}


def new_run(root, kind):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    directory = Path(root) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    record = {"run_id": run_id, "kind": kind, "status": "RUNNING", "started_utc": utc_now(), "complete": False,
              "python": sys.version, "interpreter": sys.executable, "platform": platform.platform(),
              "command_argv": sys.argv, "cwd": str(Path.cwd())}
    write_json(directory / "result.json", record)
    return directory, record


def record_command(command, cwd, results_root, timeout=120, kind="test"):
    directory, record = new_run(results_root, kind)
    record.update(command_argv=list(command), cwd=str(Path(cwd).resolve()), timeout_seconds=timeout,
                  source=source_fingerprint(cwd))
    write_json(directory / "result.json", record)
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        record.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr,
                      status="PASS" if result.returncode == 0 else "FAIL")
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
        record.update(exit_code=124, status="TIMEOUT", stdout=decode(exc.stdout), stderr=decode(exc.stderr))
    except OSError as exc:
        record.update(exit_code=127, status="ERROR", stdout="", stderr=str(exc))
    record.update(duration_seconds=time.perf_counter() - started, ended_utc=utc_now(), complete=True)
    write_json(directory / "result.json", record)
    return directory / "result.json", record
