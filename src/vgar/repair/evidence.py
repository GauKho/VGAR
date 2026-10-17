"""Durable pending/terminal JSON, one directory per invocation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid


def digest(data: bytes | str) -> str:
    return 'sha256:' + hashlib.sha256(data.encode('utf-8') if isinstance(data, str) else data).hexdigest()


def encode_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
        default=lambda v: str(v) if isinstance(v, Path) else v.model_dump(mode='json')) + '\n').encode('utf-8')


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(encode_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class RunHandle:
    def __init__(self, directory, record):
        self.directory, self.record = directory, record
        self.path = directory / 'run_record.json'
        self.start = time.monotonic()
        self.save()

    def save(self):
        atomic_json(self.path, self.record)

    def stage(self, name, value):
        self.record['stages'][name] = value
        self.save()

    def finish(self, status, *, before_publish=None, **values):
        if self.record['complete']:
            raise ValueError('Run already finalized')
        self.record.update(status=status, complete=True, ended_utc=datetime.now(timezone.utc).isoformat(),
                           duration_ms=round((time.monotonic()-self.start)*1000), **values)
        lines = [f"# {self.record['kind']} — {status}", '', f"Run: {self.record['run_id']}",
                 f"Task: {self.record.get('task_id')}", f"Mode: {self.record.get('mode')}",
                 f"Reason: {self.record.get('reason')}", '', '## Stages', '']
        for name, stage in self.record['stages'].items():
            lines.append(f"- {name}: {stage.get('status', 'recorded')}; {stage.get('duration_ms')} ms")
        lines.extend(['', 'Canonical details: `run_record.json`. No omitted failure is counted as success.'])
        (self.directory / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        if before_publish:
            before_publish(self.record)
        self.save()


def begin_run(root: Path, kind: str, **metadata) -> RunHandle:
    now = datetime.now(timezone.utc)
    run_id = f'{now:%Y%m%dT%H%M%S%fZ}-' + uuid.uuid4().hex[:12]
    directory = Path(root).resolve() / run_id
    directory.mkdir(parents=True, exist_ok=False)
    return RunHandle(directory, dict(run_id=run_id, kind=kind, status='NOT_RUN', complete=False,
        started_utc=now.isoformat(), ended_utc=None, duration_ms=None,
        interpreter=sys.executable, python=sys.version, stages={}, **metadata))



def load_run(directory: Path) -> RunHandle:
    """Re-open a run written by begin_run in another process; duration_ms keeps counting from started_utc."""
    directory = Path(directory).resolve()
    record = json.loads((directory / 'run_record.json').read_text(encoding='utf-8'))
    handle = RunHandle(directory, record)
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(record['started_utc'])).total_seconds()
    handle.start = time.monotonic() - max(elapsed, 0.0)
    return handle
