"""Issue: drawing an image with a huge value range under LogNorm fails with
"ValueError: Invalid vmin or vmax" inside LogNorm.__call__ (test_huge_range_log)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import colors  # noqa: E402


def test_huge_range_log_image_draws():
    data = np.full((5, 5), -1, dtype=np.float64)
    data[0:2, :] = 1E20
    fig, ax = plt.subplots()
    ax.imshow(data, norm=colors.LogNorm(vmin=100, vmax=data.max()), interpolation='nearest', cmap='viridis')
    fig.canvas.draw()
    plt.close(fig)
