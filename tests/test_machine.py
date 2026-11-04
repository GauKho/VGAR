"""Spec 2026-11-03-m3-w12-trace §4 E5: machine and model placement; never raises."""
from types import SimpleNamespace

from vgar.observability.machine import machine_info


class _Param:
    def __init__(self, device, n):
        self.device, self.n = SimpleNamespace(type=device), n

    def numel(self):
        return self.n


class FakeModel:
    def __init__(self, parts):
        self.parts = [_Param(d, n) for d, n in parts]

    def parameters(self):
        return iter(self.parts)


def test_machine_info_keys_and_no_model_placement():
    info = machine_info(None)
    assert set(info) == {"gpu", "vram_mib", "ram_gib", "placement"} and info["placement"] is None


def test_placement_from_parameter_devices():
    assert machine_info(FakeModel([("cuda", 71), ("meta", 29)]))["placement"] == {"gpu_pct": 71.0, "offload_pct": 29.0}


def test_broken_model_gives_null_placement():
    assert machine_info(object())["placement"] is None
