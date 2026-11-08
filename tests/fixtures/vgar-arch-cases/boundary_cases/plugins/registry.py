from storage.base import BaseStore


class Plugin(BaseStore):
    def run(self):
        return self.flush()  # expect: storage.base.BaseStore.flush


class Worker:
    def process(self, value):
        return value
