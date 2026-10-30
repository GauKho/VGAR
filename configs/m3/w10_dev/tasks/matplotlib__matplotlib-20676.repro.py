"""Issue: an interactive SpanSelector expands the axes x limits to include 0."""
import matplotlib

matplotlib.use('Agg')
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.widgets import SpanSelector  # noqa: E402


def test_interactive_span_selector_keeps_axes_limits():
    fig, ax = plt.subplots()
    ax.plot([10, 20], [10, 20])
    expected = ax.get_xlim()
    SpanSelector(ax, print, 'horizontal', interactive=True)
    fig.canvas.draw()
    assert ax.get_xlim() == expected
