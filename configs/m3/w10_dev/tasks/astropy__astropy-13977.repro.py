"""Issue: Quantity.__array_ufunc__ raises ValueError for an incompatible duck-typed input with different units
instead of returning NotImplemented, so the duck type's reflected operator is never tried."""
import dataclasses

import numpy as np
import astropy.units as u


@dataclasses.dataclass
class DuckArray(np.lib.mixins.NDArrayOperatorsMixin):
    ndarray: u.Quantity

    @property
    def unit(self):
        return self.ndarray.unit

    def __array_ufunc__(self, function, method, *inputs, **kwargs):
        inputs = [inp.ndarray if isinstance(inp, DuckArray) else inp for inp in inputs]
        for inp in inputs:
            if isinstance(inp, np.ndarray):
                result = inp.__array_ufunc__(function, method, *inputs, **kwargs)
                if result is not NotImplemented:
                    return DuckArray(result)
        return NotImplemented


def test_quantity_defers_to_duck_type_with_different_units():
    result = (1 * u.m) + DuckArray(1 * u.mm)
    assert isinstance(result, DuckArray)
    assert u.allclose(result.ndarray, 1001 * u.mm)
