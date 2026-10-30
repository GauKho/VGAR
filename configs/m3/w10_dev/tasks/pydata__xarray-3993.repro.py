"""Issue: DataArray.integrate should take `coord` (like Dataset.integrate and differentiate), not `dim`."""
import numpy as np
import xarray as xr


def test_dataarray_integrate_accepts_coord():
    da = xr.DataArray(np.arange(4.0), dims='x', coords={'x': [0.0, 1.0, 2.0, 3.0]})
    assert float(da.integrate(coord='x')) == float(da.to_dataset(name='v').integrate(coord='x')['v'])
