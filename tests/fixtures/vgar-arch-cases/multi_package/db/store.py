from app.parser import normalize


class Store:
    def put(self, value):
        return normalize(value)


class _Cache:
    def get(self):
        return 1


def load_user(user):
    return Store().put(user)


def save_user(user):
    return user
