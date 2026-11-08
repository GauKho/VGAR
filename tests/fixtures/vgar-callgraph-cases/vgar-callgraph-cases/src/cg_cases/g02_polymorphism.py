"""Group 2: polymorphism through parameters and attributes.

Name matching sees 3 candidates for every `.check()` here; the right answer
depends on which types actually flow in.
"""
from cg_cases.repos import CacheRepo, OrderRepo, UserRepo


def run_single(repo):
    # Only ever called with UserRepo.
    return repo.check()  # expect: cg_cases.repos.UserRepo.check


def run_multi(repo):
    # Called with UserRepo and OrderRepo: union of both, never CacheRepo.
    return repo.check()  # expect: cg_cases.repos.UserRepo.check, cg_cases.repos.OrderRepo.check


def run_typed(repo: CacheRepo):
    # Type comes from the annotation (and the actual argument agrees).
    return repo.check()  # expect: cg_cases.repos.CacheRepo.check


def run_each(repos):
    results = []
    for repo in repos:
        value = repo.check()  # expect: cg_cases.repos.UserRepo.check, cg_cases.repos.OrderRepo.check, cg_cases.repos.CacheRepo.check
        results.append(value)
    return results


class Service:
    def __init__(self, repo):
        self.repo = repo

    def go(self):
        # Type flows through an attribute set in __init__.
        return self.repo.check()  # expect: cg_cases.repos.OrderRepo.check


def main():
    user = UserRepo()
    order = OrderRepo()
    cache = CacheRepo()
    run_single(user)
    run_multi(user)
    run_multi(order)
    run_typed(cache)
    run_each([user, order, cache])
    service = Service(order)
    return service.go()
