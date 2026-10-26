"""Reproduction written from the issue text only (DataArray.quantile does not honor keep_attrs)."""
import xarray as xr


def test_quantile_keeps_attrs():
    da = xr.DataArray([0, 0], dims="x", attrs={"units": "K"})
    out = da.quantile(0.9, dim="x", keep_attrs=True)
    assert dict(out.attrs) == {"units": "K"}
