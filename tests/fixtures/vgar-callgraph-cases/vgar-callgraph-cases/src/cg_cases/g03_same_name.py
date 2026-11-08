"""Group 3: several same-named calls inside one function.

Tests whether per-function results are attached to the right CallSite.
"""
from cg_cases import html_tools, text_tools
from cg_cases.repos import CacheRepo, OrderRepo, UserRepo


def compare(a, b):
    first = a.check()  # expect: cg_cases.repos.UserRepo.check
    second = b.check()  # expect: cg_cases.repos.OrderRepo.check
    return first, second


def rebind():
    # Same variable, rebound sequentially (no branch): flow-sensitive answer.
    repo = UserRepo()
    first = repo.check()  # expect: cg_cases.repos.UserRepo.check
    repo = CacheRepo()
    second = repo.check()  # expect: cg_cases.repos.CacheRepo.check
    return first, second


def render_both(value):
    # Same function name in two different modules.
    plain = text_tools.render(value)  # expect: cg_cases.text_tools.render
    rich = html_tools.render(value)  # expect: cg_cases.html_tools.render
    return plain, rich


def main():
    user = UserRepo()
    order = OrderRepo()
    compare(user, order)
    rebind()
    return render_both("x")
