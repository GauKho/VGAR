"""Local OS-backed process/thread locks. Persistent lock files are not stale grants."""
import hashlib
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

_CACHE = {}
_CACHE_LOCK = threading.Lock()


def is_reparse(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except FileNotFoundError:
        return False


def no_links(path: Path) -> Path:
    path = Path(path).absolute()
    if any(is_reparse(p) for p in (*reversed(path.parents), path)):
        raise ValueError("Linked/reparse paths are not allowed")
    return path


def lock_key(path: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(path.resolve())).encode("utf-8")).hexdigest()


@contextmanager
def locked(path: Path, *, timeout: float = 10, deadline: float | None = None, cancel_event=None):
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    no_links(path)
    key = (os.getpid(), str(path))
    with _CACHE_LOCK:
        lock = _CACHE.setdefault(key, FileLock(str(path), thread_local=True))
    end = min(time.time()+timeout, deadline if deadline is not None else float("inf"))
    pause = cancel_event or threading.Event()
    while True:
        if pause.is_set():
            raise ValueError("Request cancelled while waiting for lock")
        try:
            lock.acquire(timeout=0)
            break
        except Timeout:
            if time.time() >= end:
                raise TimeoutError("Security lock deadline exhausted") from None
            pause.wait(min(.02, max(0, end-time.time())))
    try:
        no_links(path)
        yield
    finally:
        lock.release()
