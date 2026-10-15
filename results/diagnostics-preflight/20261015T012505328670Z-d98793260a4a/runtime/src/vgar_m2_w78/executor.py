"""Bounded fixed-argv process execution; Native is not an OS security sandbox."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class _WindowsJob:
    """Assign a suspended process before allowing it to spawn descendants."""
    def __init__(self, process):
        import ctypes
        from ctypes import wintypes as w
        class Limits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', w.DWORD), ('min', ctypes.c_size_t), ('max', ctypes.c_size_t),
                ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Limits), ('io', IO), ('process_mem', ctypes.c_size_t),
                       ('job_mem', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = ctypes.c_void_p
        kernel.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, w.UINT]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel, self.handle = kernel, kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), 'CreateJobObject failed')
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(self.handle, int(process._handle))):
            self.close()
            raise OSError(ctypes.get_last_error(), 'Cannot confine child to Windows job')
        resume = ctypes.WinDLL('ntdll').NtResumeProcess
        resume.argtypes = [ctypes.c_void_p]
        resume.restype = ctypes.c_long
        if resume(int(process._handle)) < 0:
            self.close()
            raise OSError('Cannot resume confined child')

    def close(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def clean_environment(extra=None):
    environment = {k: v for k, v in os.environ.items()
                   if not any(word in k.upper() for word in ('TOKEN', 'PASSWORD', 'SECRET', 'API_KEY'))}
    environment.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    environment.update(extra or {})
    return environment


def run_bounded(argv: tuple[str, ...], cwd: Path, timeout_seconds: float,
                *, output_cap=8 * 1024 * 1024, environment=None) -> dict:
    if not argv or any(not isinstance(a, str) or '\0' in a for a in argv) or timeout_seconds <= 0:
        raise ValueError('Fixed argv and positive timeout required')
    cwd = Path(cwd).resolve(strict=True)
    record = dict(argv=list(argv), command=subprocess.list2cmdline(argv), cwd=str(cwd),
                  interpreter=argv[0], started_utc=utc_now(), timeout_seconds=timeout_seconds,
                  exit_code=None, stdout='', stderr='', timed_out=False, output_truncated=False,
                  complete=True, stdout_bytes=0, stderr_bytes=0)
    start = time.monotonic()
    process, job = None, None
    try:
        with tempfile.TemporaryDirectory(prefix='m2-output-') as folder:
            outpath, errpath = Path(folder) / 'stdout.bin', Path(folder) / 'stderr.bin'
            with outpath.open('wb') as out, errpath.open('wb') as err:
                process = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err,
                    env=clean_environment(environment), shell=False,
                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | 0x4) if os.name == 'nt' else 0,
                    start_new_session=os.name != 'nt')
                if os.name == 'nt':
                    job = _WindowsJob(process)
                while process.poll() is None:
                    if time.monotonic() - start >= timeout_seconds:
                        record['timed_out'] = True
                        break
                    if max(outpath.stat().st_size, errpath.stat().st_size) > output_cap:
                        record['output_truncated'] = True
                        break
                    time.sleep(.02)
                # Terminate descendants even if their immediate parent finished.
                if job:
                    job.close()
                elif os.name != 'nt':
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
            record['exit_code'] = process.returncode
            for label, path in (('stdout', outpath), ('stderr', errpath)):
                record[label + '_bytes'] = path.stat().st_size
                with path.open('rb') as stream:
                    data = stream.read(output_cap)
                record[label] = data.decode('utf-8', errors='replace')
                record['output_truncated'] |= path.stat().st_size > output_cap
            record['complete'] = not (record['timed_out'] or record['output_truncated'])
            record['status'] = ('ERROR' if not record['complete'] else 'PASS' if process.returncode == 0 else 'FAIL')
    except (OSError, subprocess.SubprocessError) as error:
        record.update(status='ERROR', complete=False, stderr=str(error), error_type=type(error).__name__)
    finally:
        if job:
            job.close()
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        record.update(ended_utc=utc_now(), duration_ms=round((time.monotonic()-start)*1000))
    return record


class NativeExecutor:
    def __init__(self, lease=None, output_cap=8 * 1024 * 1024):
        self.lease, self.output_cap = lease, output_cap

    def run(self, argv: tuple[str, ...], cwd: Path, timeout_seconds: float) -> dict:
        if self.lease is None or not self.lease.active or Path(cwd).resolve() != self.lease.path:
            raise ValueError('Executor requires an active owned workspace')
        if argv[0] == sys.executable:
            if len(argv) < 3 or argv[1:3] not in (('-m', 'pytest'), ('-m', 'mypy'), ('-m', 'ruff')):
                raise ValueError('Command not allowed')
        elif argv[0] == 'git':
            if len(argv) < 2 or argv[1] not in ('apply', 'diff', 'status'):
                raise ValueError('Git command not allowed')
        else:
            raise ValueError('Interpreter/command not allowed')
        return run_bounded(argv, cwd, timeout_seconds, output_cap=self.output_cap)

