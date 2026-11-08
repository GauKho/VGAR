from app.parser import normalize
from db.store import load_user, save_user

__all__ = ["login", "_audit"]


def login(name):
    user = normalize(name)
    _audit(user)
    return load_user(user)


def _audit(user):
    return save_user(user)


def _hidden():
    def inner():
        return 1

    return inner()
