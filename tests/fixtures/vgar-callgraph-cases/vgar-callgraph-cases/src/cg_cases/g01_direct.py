"""Group 1: direct calls, baseline. Every tool should get these right."""
from cg_cases import helpers
from cg_cases.helpers import normalize


def _local_step(value):
    return value + 1


class Counter:
    def __init__(self):
        self.count = 0

    def bump(self):
        self.count = _local_step(self.count)  # expect: cg_cases.g01_direct._local_step
        return self.count

    def bump_twice(self):
        self.bump()  # expect: cg_cases.g01_direct.Counter.bump
        return self.bump()


def main():
    text = normalize("  Hello ")  # expect: cg_cases.helpers.normalize
    size = helpers.measure(text)  # expect: cg_cases.helpers.measure
    counter = Counter()  # expect: cg_cases.g01_direct.Counter.__init__
    counter.bump_twice()  # expect: cg_cases.g01_direct.Counter.bump_twice
    return size
