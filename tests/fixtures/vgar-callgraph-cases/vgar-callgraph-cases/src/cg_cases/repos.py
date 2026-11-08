"""Shared classes used by several groups. `check` is defined only here (3 classes)."""


class UserRepo:
    def check(self):
        return "user"


class OrderRepo:
    def check(self):
        return "order"


class CacheRepo:
    def check(self):
        return "cache"
