"""Group 9: candidate threshold.

`alpha` is defined in exactly 5 classes, `beta` in exactly 6, nowhere else in
the repo. The annotations give the TRUE target; whether the static mode emits
an edge at 5 vs 6 candidates is a spec test, scored separately.
"""


class Alpha1:
    def alpha(self):
        return 1


class Alpha2:
    def alpha(self):
        return 2


class Alpha3:
    def alpha(self):
        return 3


class Alpha4:
    def alpha(self):
        return 4


class Alpha5:
    def alpha(self):
        return 5


class Beta1:
    def beta(self):
        return 1


class Beta2:
    def beta(self):
        return 2


class Beta3:
    def beta(self):
        return 3


class Beta4:
    def beta(self):
        return 4


class Beta5:
    def beta(self):
        return 5


class Beta6:
    def beta(self):
        return 6


def call_alpha(obj):
    return obj.alpha()  # expect: cg_cases.g09_threshold.Alpha3.alpha


def call_beta(obj):
    return obj.beta()  # expect: cg_cases.g09_threshold.Beta4.beta


def main():
    call_alpha(Alpha3())
    call_beta(Beta4())
    local_a = Alpha2()
    local_a.alpha()  # expect: cg_cases.g09_threshold.Alpha2.alpha
    local_b = Beta6()
    return local_b.beta()  # expect: cg_cases.g09_threshold.Beta6.beta
