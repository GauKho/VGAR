"""Issue: hist() ignores range=(0, 1) when density=True; the bins should start at 0 and end at 1."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def test_hist_density_respects_range():
    _, bins, _ = plt.hist(np.random.RandomState(0).rand(10), 'auto', range=(0, 1), density=True)
    plt.close('all')
    assert bins[0] == 0
    assert bins[-1] == 1
