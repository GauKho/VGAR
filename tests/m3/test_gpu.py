"""M3-W9-2: device-wide VRAM peak from nvidia-smi samples; unknown is None, never 0."""
from types import SimpleNamespace

from vgar.evaluation.repair import gpu


def sampler_with(monkeypatch, outputs):
    replies = iter(outputs)
    monkeypatch.setattr(gpu.shutil, 'which', lambda name: '/usr/bin/nvidia-smi')
    monkeypatch.setattr(gpu.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=next(replies, outputs[-1])))
    return gpu.GpuPeakSampler(interval=0.01)


def test_gpu_sampler_returns_peak(monkeypatch):
    sampler = sampler_with(monkeypatch, ['1000\n', '3000\n', '2000\n'])
    sampler.start()
    sampler._sample()
    sampler._sample()
    assert sampler.stop() == 3000


def test_gpu_sampler_without_nvidia_smi_is_none(monkeypatch):
    monkeypatch.setattr(gpu.shutil, 'which', lambda name: None)
    sampler = gpu.GpuPeakSampler()
    sampler.start()
    assert sampler.stop() is None


def test_gpu_sampler_garbage_output_is_none(monkeypatch):
    sampler = sampler_with(monkeypatch, ['[N/A]\n'])
    sampler.start()
    assert sampler.stop() is None
