from storage.base import BaseStore
from storage.sql import SqlStore, format_total as storage_format


def place_order(item):
    store = SqlStore()  # expect: storage.sql.SqlStore.__init__
    save_with(store, item)  # expect: services.orders.save_with
    return storage_format(item)  # expect: storage.sql.format_total


def save_with(store: BaseStore, item):
    return store.save(item)  # expect: storage.sql.SqlStore.save, storage.memory.MemoryStore.save


def run_hook(fn):
    return fn()  # expect: storage.memory.snapshot
