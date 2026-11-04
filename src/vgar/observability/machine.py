"""Machine and model placement for a run header (spec 2026-11-03-m3-w12-trace §4 E5). Never raises."""
from __future__ import annotations

from pathlib import Path


def _gpu() -> tuple[str | None, int | None]:
    try:
        import torch
        if not torch.cuda.is_available():
            return None, None
        props = torch.cuda.get_device_properties(0)
        return props.name, round(props.total_memory / 2**20)
    except Exception:
        return None, None


def _ram_gib() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 2**20, 1)
    except Exception:
        return None
    return None


def _placement(hf_model) -> dict | None:
    """Share of parameters on the GPU; the rest is offloaded (cpu, or meta under accelerate offload)."""
    if hf_model is None:
        return None
    try:
        on_gpu = total = 0
        for param in hf_model.parameters():
            n = param.numel()
            total += n
            on_gpu += n if param.device.type == "cuda" else 0
        if not total:
            return None
        gpu = round(100 * on_gpu / total, 1)
        return {"gpu_pct": gpu, "offload_pct": round(100 - gpu, 1)}
    except Exception:
        return None


def machine_info(hf_model=None) -> dict:
    gpu, vram = _gpu()
    return {"gpu": gpu, "vram_mib": vram, "ram_gib": _ram_gib(), "placement": _placement(hf_model)}
