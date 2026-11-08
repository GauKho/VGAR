from storage.base import BaseStore


class MemoryStore(BaseStore):
    def __init__(self):
        self.rows = []

    def save(self, item):
        return item


def snapshot():
    return MemoryStore()  # expect: storage.memory.MemoryStore.__init__
