from api.handlers import create_order, dispatch, dynamic, hook_order, late
from plugins.registry import Plugin, Worker
from services.orders import save_with
from services.pricing import outer
from storage.memory import MemoryStore
from storage.sql import SqlStore

create_order(5)
hook_order()
dispatch(Worker())
late()
dynamic("_secret")
save_with(SqlStore(), 1)
save_with(MemoryStore(), 1)
Plugin().run()
outer()
