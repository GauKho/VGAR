"""T3 oracle contract only; real Astropy base/gold execution belongs in Docker."""
from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest


REPRO = Path(__file__).resolve().parents[3] / 'configs/m3/w10_dev/tasks/astropy__astropy-13033.repro.py'


def run_oracle(monkeypatch, message):
    # Astropy is intentionally not imported into the Windows controller. These
    # boundary doubles provide only a fixed exception for the real repro oracle.
    numpy, time_module, timeseries = (ModuleType(name) for name in
                                     ('numpy', 'astropy.time', 'astropy.timeseries'))
    numpy.arange = lambda *a: [100000, 100001, 100002]
    time_module.Time = lambda values, **kw: values

    class FixedExceptionSeries:
        def __init__(self, **kwargs):
            pass

        def remove_column(self, name):
            raise ValueError(message)

    timeseries.TimeSeries = FixedExceptionSeries
    for module in (numpy, time_module, timeseries):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    namespace = runpy.run_path(str(REPRO))
    namespace['test_missing_required_column_message_names_the_column']()


@pytest.mark.parametrize('message', [
    "TimeSeries object is invalid - expected ['time', 'flux'] as the first columns but found 'time'",
    "TimeSeries object is invalid - expected ['time', 'flux'] as the first columns but found ['time']",
])
def test_repro_accepts_informative_required_columns_even_when_actual_is_time(monkeypatch, message):
    run_oracle(monkeypatch, message)


@pytest.mark.parametrize('message', [
    "TimeSeries object is invalid - expected 'time' as the first columns but found 'time'",
    "TimeSeries object is invalid - expected 'time' as the first columns but found 'flux'",
    "TimeSeries object is invalid - expected ['time', 'flux'] as the first columns but found 'banana'",
    "TimeSeries object is invalid - expected ['time', 'flux']",
])
def test_repro_rejects_missing_expected_column_or_incorrect_actual_evidence(monkeypatch, message):
    with pytest.raises(AssertionError):
        run_oracle(monkeypatch, message)
