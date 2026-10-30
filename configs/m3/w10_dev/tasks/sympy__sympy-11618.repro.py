"""Issue: Point(2, 0).distance(Point(1, 0, 2)) ignores the third dimension and returns 1 instead of sqrt(5)."""
from sympy import sqrt
from sympy.geometry import Point


def test_distance_uses_all_dimensions():
    assert Point(2, 0).distance(Point(1, 0, 2)) == sqrt(5)
