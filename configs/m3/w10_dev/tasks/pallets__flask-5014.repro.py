"""Issue: a Blueprint with an empty name should raise ValueError."""
import pytest

import flask


def test_empty_blueprint_name_is_rejected():
    with pytest.raises(ValueError):
        flask.Blueprint('', __name__)
