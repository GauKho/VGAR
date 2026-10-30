from pkg.core import helper


def use():
    return helper(2)


def outer():
    return use() + len([])
