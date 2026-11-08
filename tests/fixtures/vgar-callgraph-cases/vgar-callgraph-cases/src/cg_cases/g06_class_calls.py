"""Group 6: calling a class.

Rule 6: annotate Foo.__init__ when the class defines __init__; no annotation
when nothing in the MRO defines one. Child() below inherits __init__ from
Parent, so its target is Parent.__init__ (see README, open question).
"""


class WithInit:
    def __init__(self, value):
        self.value = value


class NoInit:
    label = "plain"


class Parent:
    def __init__(self):
        self.ready = True


class Child(Parent):
    pass


class GrandChild(Child):
    def __init__(self):
        super().__init__()  # expect: cg_cases.g06_class_calls.Parent.__init__
        self.extra = 1


def main():
    first = WithInit(1)  # expect: cg_cases.g06_class_calls.WithInit.__init__
    plain = NoInit()
    child = Child()  # expect: cg_cases.g06_class_calls.Parent.__init__
    grand = GrandChild()  # expect: cg_cases.g06_class_calls.GrandChild.__init__
    factory = WithInit
    second = factory(2)  # expect: cg_cases.g06_class_calls.WithInit.__init__
    return first, plain, child, grand, second
