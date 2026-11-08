from services.pricing import discount
from storage.base import BaseStore


class SqlStore(BaseStore):
    def __init__(self):
        self.rows = []

    def save(self, item):
        return discount(item)  # expect: services.pricing.discount


def connect():
    return SqlStore()  # expect: storage.sql.SqlStore.__init__


def format_total(value):
    return value
