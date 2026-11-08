import json

import services.pricing as pricing
from services.orders import place_order, run_hook
from services.pricing import _internal, _secret, discount
from storage.memory import snapshot


def create_order(item):
    place_order(item)  # expect: services.orders.place_order
    pricing.discount(2)  # expect: services.pricing.discount
    discount(3)  # expect: services.pricing.discount
    _internal()  # expect: services.pricing._internal
    _secret()  # expect: services.pricing._secret
    return json.dumps(item)  # expect: external


def hook_order():
    return run_hook(snapshot)  # expect: services.orders.run_hook


def dispatch(obj):
    return obj.process(1)  # expect: plugins.registry.Worker.process


def late():
    from storage.sql import connect

    return connect()  # expect: storage.sql.connect


def dynamic(name):
    target = getattr(pricing, name)
    return target()  # expect: unknown
