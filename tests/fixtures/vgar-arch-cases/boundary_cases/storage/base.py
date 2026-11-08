class BaseStore:
    def save(self, item):
        raise NotImplementedError

    def flush(self):
        return True
