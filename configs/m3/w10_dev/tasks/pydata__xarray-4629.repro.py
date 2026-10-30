"""Issue: merge(combine_attrs='override') references the first object's attrs instead of copying them."""
import xarray as xr


def test_merge_override_copies_attrs():
    xds1 = xr.Dataset(attrs={'a': 'b'})
    xds2 = xr.Dataset(attrs={'a': 'c'})
    xds3 = xr.merge([xds1, xds2], combine_attrs='override')
    xds3.attrs['a'] = 'd'
    assert xds1.attrs['a'] == 'b'
