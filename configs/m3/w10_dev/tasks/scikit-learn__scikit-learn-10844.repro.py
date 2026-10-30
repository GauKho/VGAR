"""Issue: fowlkes_mallows_score computes tk / np.sqrt(pk * qk); pk * qk overflows the integer type for big
clusters and the score becomes nan (RuntimeWarning: overflow) instead of a float."""
import warnings

import numpy as np
from sklearn.metrics import fowlkes_mallows_score


def test_fowlkes_mallows_score_large_clusters_does_not_overflow():
    labels = np.zeros(100000, dtype=int)
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        score = fowlkes_mallows_score(labels, labels)
    assert score == 1.0
