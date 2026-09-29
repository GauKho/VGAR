from __future__ import annotations

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from vgar.models.huggingface.hf_model import create_local_qwen_model



def create_core_model() -> BaseChatModel:
    model = create_local_qwen_model()

    if not isinstance(model, BaseChatModel):
        raise TypeError(
            "Core model must implement BaseChatModel."
        )

    return model