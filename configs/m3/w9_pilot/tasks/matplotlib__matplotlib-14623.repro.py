"""Reproduction written from the issue text only (inverting a log axis via its limits)."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


def test_log_axis_inverted_by_limits():
    y = np.linspace(1000e2, 1, 100)
    x = np.exp(-np.linspace(0, 1, y.size))
    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_yscale("log")
    ax.set_ylim(y.max(), y.min())
    assert ax.yaxis_inverted()
    plt.close(fig)
