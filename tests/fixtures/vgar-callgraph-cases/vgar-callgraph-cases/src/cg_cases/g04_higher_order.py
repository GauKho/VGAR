"""Group 4: higher-order calls (callbacks, dispatch tables, aliases, closures)."""
import functools


def on_success(value):
    return f"ok:{value}"


def on_failure(value):
    return f"fail:{value}"


def handle_create():
    return "created"


def handle_delete():
    return "deleted"


HANDLERS = {"create": handle_create, "delete": handle_delete}


def apply(callback, value):
    return callback(value)  # expect: cg_cases.g04_higher_order.on_success, cg_cases.g04_higher_order.on_failure


def dispatch(action):
    return HANDLERS[action]()  # expect: cg_cases.g04_higher_order.handle_create, cg_cases.g04_higher_order.handle_delete


def make_multiplier(factor):
    def multiply(value):
        return value * factor

    return multiply


def main():
    apply(on_success, 1)
    apply(on_failure, 2)
    dispatch("create")
    dispatch("delete")
    step = on_success
    step(3)  # expect: cg_cases.g04_higher_order.on_success
    times3 = make_multiplier(3)
    times3(4)  # expect: cg_cases.g04_higher_order.make_multiplier.<locals>.multiply
    bound = functools.partial(on_failure, 5)
    bound()  # expect: cg_cases.g04_higher_order.on_failure
    square = lambda v: v * v  # noqa: E731
    return square(2)  # expect: cg_cases.g04_higher_order.main.<locals>.<lambda>
