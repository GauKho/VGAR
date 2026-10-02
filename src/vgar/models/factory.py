from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from vgar.config.settings import ModelSettings, get_settings


def create_core_model(settings: ModelSettings | None = None) -> BaseChatModel:
    """The only place that turns ModelSettings into a chat model."""
    settings = settings or get_settings().model

    if settings.provider != "huggingface":
        raise ValueError(f"Unsupported VGAR_MODEL_PROVIDER: {settings.provider!r}")
    if settings.temperature != 0.0:
        raise ValueError("Local HF model is greedy-only; set VGAR_TEMPERATURE=0")

    # Lazy: torch/transformers are only imported when a real model is requested.
    from vgar.models.huggingface.hf_model import create_local_chat_model

    model = create_local_chat_model(
        model_id=settings.model_id,
        max_new_tokens=settings.max_new_tokens,
        device_map=settings.device_map,
        torch_dtype=settings.torch_dtype,
    )
    if not isinstance(model, BaseChatModel):
        raise TypeError("Core model must implement BaseChatModel.")
    return model
