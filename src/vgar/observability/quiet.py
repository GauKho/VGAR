"""Drop known library noise from the console (spec 2026-11-03-m3-w12-trace §5 P8); never hides VGAR's own logs."""
from __future__ import annotations

import logging

TRANSFORMERS_NOISE = ("`torch_dtype` is deprecated",)


class DropMessages(logging.Filter):
    def __init__(self, substrings: tuple[str, ...]):
        super().__init__()
        self.substrings = substrings

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(text in message for text in self.substrings)


def quiet_transformers() -> None:
    """transformers logs through its own handler on the 'transformers' logger; filter there."""
    try:
        from transformers.utils import logging as hf_logging
        hf_logging.get_logger()  # makes sure the library handler exists
    except Exception:
        return
    drop = DropMessages(TRANSFORMERS_NOISE)
    for handler in logging.getLogger("transformers").handlers:
        if not any(isinstance(f, DropMessages) for f in handler.filters):
            handler.addFilter(drop)
