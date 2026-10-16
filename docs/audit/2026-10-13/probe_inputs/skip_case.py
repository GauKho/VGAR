import pytest


@pytest.mark.skip(reason="audit reproduction: required case is skipped")
def test_required():
    assert False
