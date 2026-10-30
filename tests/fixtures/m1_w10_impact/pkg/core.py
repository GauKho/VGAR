class Base:
    def run(self):
        return helper(1)


class Child(Base):
    pass


def helper(x):
    return x + 1


def _private(x):
    return helper(x)
