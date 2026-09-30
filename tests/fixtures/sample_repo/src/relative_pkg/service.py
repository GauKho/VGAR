from .base import RelativeBase


class RelativeService(RelativeBase):
    @classmethod
    def create(cls) -> "RelativeService":
        return cls()
