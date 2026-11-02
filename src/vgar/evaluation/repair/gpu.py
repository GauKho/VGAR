"""Device-wide VRAM peak by polling nvidia-smi: the model runs in a worker process the runner cannot inspect."""
from __future__ import annotations

import shutil
import subprocess
import threading

QUERY = ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits']


class GpuPeakSampler:
    """Max successful memory.used (MiB) across GPUs/polls; None until a valid sample.

    samples_failed counts failed polls, including a missing executable at start.
    The legacy ok flag describes complete sampling; it no longer gates the peak.
    """

    def __init__(self, interval: float = 0.5):
        self.interval, self.peak, self.ok = interval, None, True
        self.samples_failed = 0
        self._stop, self._thread = threading.Event(), None

    def _sample(self) -> None:
        try:
            result = subprocess.run(QUERY, capture_output=True, text=True, timeout=5, check=False)
            values = [int(v) for v in result.stdout.split()] if result.returncode == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError):
            values = []
        if not values or any(value < 0 for value in values):
            self.ok = False
            self.samples_failed += 1
            return
        self.peak = max(self.peak or 0, *values)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._sample()

    def start(self) -> None:
        if shutil.which('nvidia-smi') is None:
            self.ok = False
            self.samples_failed += 1
            return
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> int | None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        return self.peak
