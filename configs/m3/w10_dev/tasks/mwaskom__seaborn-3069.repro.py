"""Issue: a Nominal scale should be drawn like a categorical axis: limits at +/- 0.5 around the first and
last tick, no grid, and an inverted axis when it is on y."""
import matplotlib
matplotlib.use('Agg')
import pandas as pd  # noqa: E402
import seaborn.objects as so  # noqa: E402

# Environment shim, not part of the issue: the testbed's pandas 2.0 removed the option name that seaborn
# 0.12 still sets while splitting layer data. Re-register it so a plot can be drawn at all.
try:
    pd.get_option('mode.use_inf_as_null')
except Exception:
    from pandas._config.config import register_option
    register_option('mode.use_inf_as_null', False)


def _axes(**variables):
    plotter = so.Plot(**variables).add(so.Dot()).plot()
    return plotter._figure.axes[0]


def test_nominal_x_axis_limits_like_categorical():
    ax = _axes(x=['a', 'b', 'c'], y=[1, 2, 3])
    assert tuple(ax.get_xlim()) == (-0.5, 2.5)


def test_nominal_y_axis_is_inverted():
    ax = _axes(x=[1, 2, 3], y=['a', 'b', 'c'])
    assert tuple(ax.get_ylim()) == (2.5, -0.5)
