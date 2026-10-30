"""Issue: Permutation([[0, 1], [0, 1]]) raises ValueError; non-disjoint cycles should be applied left to right."""
from sympy.combinatorics.permutations import Permutation


def test_non_disjoint_cycles_build_their_product():
    # The engine baseline accepts assertion failures only, so the issue's ValueError is reported as one.
    try:
        permutation = Permutation([[0, 1], [0, 1]])
    except ValueError as error:
        assert False, 'non-disjoint cycles rejected: %s' % error
    assert permutation == Permutation([0, 1])
