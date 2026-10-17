__all__ = [
    "create_local_chat_model",
]


def __getattr__(name):
    # Lazy: hf_model imports torch; the M2 fake/worker-host modules in this package must not.
    if name == "create_local_chat_model":
        from vgar.models.huggingface.hf_model import create_local_chat_model
        return create_local_chat_model
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
