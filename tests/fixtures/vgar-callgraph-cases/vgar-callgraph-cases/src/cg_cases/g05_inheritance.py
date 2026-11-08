"""Group 5: inheritance, override, super(), mixin MRO, classmethod, __call__."""


class BaseStore:
    def fetch(self):
        return "base"

    def describe(self):
        return "store"

    @classmethod
    def create(cls):
        return cls()


class ChildStore(BaseStore):
    def fetch(self):
        # Syntactically two calls (super() and .fetch()); only .fetch() is graded.
        parent = super().fetch()  # expect: cg_cases.g05_inheritance.BaseStore.fetch
        return "child+" + parent


class LoggingMixin:
    def fetch(self):
        return "mixin"


class MixedStore(LoggingMixin, BaseStore):
    pass


class Scorer:
    def __call__(self, value):
        return value * 2


def main():
    child = ChildStore.create()  # expect: cg_cases.g05_inheritance.BaseStore.create
    child.fetch()  # expect: cg_cases.g05_inheritance.ChildStore.fetch
    child.describe()  # expect: cg_cases.g05_inheritance.BaseStore.describe
    mixed = MixedStore()
    mixed.fetch()  # expect: cg_cases.g05_inheritance.LoggingMixin.fetch
    scorer = Scorer()
    return scorer(3)  # expect: cg_cases.g05_inheritance.Scorer.__call__
