"""Issue: collecting a test decorated with patch(new=<numpy array>) raises
"ValueError: The truth value of an array ... is ambiguous" while counting mock patch arguments."""
from unittest.mock import patch

from _pytest.compat import getfuncargnames


class ArrayLike:
    """Behaves like numpy.ndarray in comparisons: `==` gives an object whose truth value is ambiguous."""

    def __eq__(self, other):
        return Ambiguous()


class Ambiguous:
    def __bool__(self):
        raise ValueError('The truth value of an array with more than one element is ambiguous.')


def test_patch_with_array_like_new_is_collectable():
    @patch(target='os.getcwd', new=ArrayLike())
    def test_function():
        pass

    assert getfuncargnames(test_function) == ()
