"""Issue: RidgeClassifierCV rejects store_cv_values=True although cv_values_ is documented for it."""
import numpy as np
from sklearn import linear_model as lm


def test_ridge_classifier_cv_stores_cv_values():
    rng = np.random.RandomState(0)
    x = rng.randn(100, 30)
    y = np.array([0, 1] * 50)
    model = lm.RidgeClassifierCV(alphas=np.arange(0.1, 10, 1.0), store_cv_values=True).fit(x, y)
    assert hasattr(model, 'cv_values_')
