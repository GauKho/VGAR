"""C7/D14: device-wide successful-sample peak and deterministic failure counts."""
import subprocess
import threading
from types import SimpleNamespace

import pytest

from vgar.evaluation.repair import gpu


@pytest.fixture(autouse=True)
def controlled_polling(monkeypatch):
    """Value tests own every poll; a real worker is exercised separately below."""
    monkeypatch.setattr(gpu, 'threading', SimpleNamespace(Event=threading.Event,
        Thread=lambda **kwargs: SimpleNamespace(start=lambda: None, join=lambda: None)))


def sampler_with(monkeypatch, outputs):
    replies = iter(outputs)
    monkeypatch.setattr(gpu.shutil, 'which', lambda name: '/usr/bin/nvidia-smi')

    def run(argv, **kwargs):
        value = next(replies)  # unexpected extra polls fail instead of reusing a reply
        if isinstance(value, Exception):
            raise value
        code, stdout = value if isinstance(value, tuple) else (0, value)
        return subprocess.CompletedProcess(argv, code, stdout=stdout, stderr='')

    monkeypatch.setattr(gpu.subprocess, 'run', run)
    return gpu.GpuPeakSampler(interval=0.01)


def test_gpu_sampler_returns_peak(monkeypatch):
    sampler = sampler_with(monkeypatch, ['1000\n', '3000\n', '2000\n'])
    sampler.start()
    sampler._sample()
    sampler._sample()
    assert sampler.stop() == 3000
    assert sampler.samples_failed == 0


def test_gpu_sampler_without_nvidia_smi_is_none(monkeypatch):
    monkeypatch.setattr(gpu.shutil, 'which', lambda name: None)
    sampler = gpu.GpuPeakSampler()
    sampler.start()
    assert sampler.stop() is None
    assert sampler.samples_failed == 1


def test_gpu_sampler_garbage_output_is_none(monkeypatch):
    sampler = sampler_with(monkeypatch, ['[N/A]\n'])
    sampler.start()
    assert sampler.stop() is None
    assert sampler.samples_failed == 1


@pytest.mark.parametrize('outputs,peak,failed', [
    (['1000\n', '[N/A]\n', '3000\n', '2000\n'], 3000, 1),
    (['3000\n', '[N/A]\n', '\n'], 3000, 2),
    (['[N/A]\n', '2000\n'], 2000, 1),
    (['[N/A]\n', '\n', (1, '9000\n')], None, 3),
    (['0\n'], 0, 0),
    (['0\n', '[N/A]\n'], 0, 1),
    (['1000\n3000\n', '2500\n1000\n'], 3000, 0),
    (['1000\n[N/A]\n', '900\n800\n'], 900, 1),
    (['0\n0\n', '0\n'], 0, 0),
])
def test_peak_uses_successful_samples_and_counts_each_failed_poll(monkeypatch, outputs, peak, failed):
    sampler = sampler_with(monkeypatch, outputs)
    sampler.start()
    for _ in outputs[1:]:
        sampler._sample()
    assert sampler.stop() == peak
    assert sampler.samples_failed == failed


@pytest.mark.parametrize('bad', [
    '', ' \n\t', '[N/A]\n', '1.5\n', '500\nbroken\n', '-1\n', '2000\n-1\n',
    (1, '9999\n'), OSError('unreadable'), FileNotFoundError('gone after lookup'),
    subprocess.TimeoutExpired(gpu.QUERY, 5), subprocess.SubprocessError('failed'),
])
def test_failed_poll_keeps_peak_and_increments_once(monkeypatch, bad):
    sampler = sampler_with(monkeypatch, ['1200\n', bad])
    sampler.start()
    sampler._sample()
    assert sampler.stop() == 1200
    assert sampler.samples_failed == 1


def test_missing_executable_counts_one_without_query_or_thread(monkeypatch):
    monkeypatch.setattr(gpu.shutil, 'which', lambda name: None)
    def unexpected(*args, **kwargs):
        pytest.fail('Missing executable must not launch a query or polling thread')
    monkeypatch.setattr(gpu.subprocess, 'run', unexpected)
    monkeypatch.setattr(gpu.threading, 'Thread', unexpected)
    sampler = gpu.GpuPeakSampler()
    sampler.start()
    assert sampler.stop() is None
    assert sampler.stop() is None  # stop does not create another failed sample
    assert sampler.samples_failed == 1


def test_stop_before_start_is_unknown_without_a_failed_sample():
    sampler = gpu.GpuPeakSampler()
    assert sampler.stop() is None
    assert sampler.samples_failed == 0


def test_loop_has_exact_scripted_poll_count(monkeypatch):
    sampler = sampler_with(monkeypatch, ['1000\n', '[N/A]\n', '2000\n'])
    sampler.start()
    waits = iter((False, False, True))
    sampler._stop = SimpleNamespace(wait=lambda interval: next(waits), set=lambda: None)
    sampler._loop()
    assert sampler.stop() == 2000
    assert sampler.samples_failed == 1


def test_stopped_loop_does_not_take_another_sample(monkeypatch):
    sampler = sampler_with(monkeypatch, ['1000\n'])
    sampler.start()
    assert sampler.stop() == 1000
    sampler._loop()  # an extra query would exhaust the scripted responses
    assert sampler.samples_failed == 0


def test_real_worker_retains_peak_after_a_failed_poll(monkeypatch):
    monkeypatch.setattr(gpu, 'threading', threading)
    sampler = sampler_with(monkeypatch, ['1000\n', '[N/A]\n', '2300\n'])
    sampler.interval = 0
    original, completed, calls = sampler._sample, threading.Event(), []

    def sample():
        original()
        calls.append(None)
        if len(calls) == 3:
            sampler._stop.set()
            completed.set()

    monkeypatch.setattr(sampler, '_sample', sample)
    try:
        sampler.start()
        assert completed.wait(5), 'Worker did not finish its fixed three samples'
    finally:
        peak = sampler.stop()
    assert peak == 2300
    assert sampler.samples_failed == 1
    assert not sampler._thread.is_alive()
