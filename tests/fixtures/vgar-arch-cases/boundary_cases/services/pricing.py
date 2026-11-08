__all__ = ["discount", "_internal"]


def discount(value):
    return value - 1


def _internal():
    return 1


def _secret():
    return 2


def format_total(value):
    return str(value)


class _Hidden:
    def method(self):
        return 1


def outer():
    def nested():
        return 1

    return nested()  # expect: services.pricing.outer.<locals>.nested
