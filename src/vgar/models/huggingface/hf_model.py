from __future__ import annotations

import torch

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline,
)

from langchain_huggingface import (
    HuggingFacePipeline,
)

from vgar.models.huggingface.local_hf_chat_model import LocalChatModel


DEFAULT_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"


def create_local_chat_model(
    model_id: str = DEFAULT_MODEL_ID,
    max_new_tokens: int = 256,
) -> LocalChatModel:

    print(
        f"[HF] Loading tokenizer: {model_id}"
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
    )

    if not tokenizer.chat_template:
        raise RuntimeError(
            f"Model {model_id!r} does not provide "
            "a chat template."
        )

    print(
        f"[HF] Loading model: {model_id}"
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
    )

    print(
        "[HF] CUDA available:",
        torch.cuda.is_available(),
    )

    print(
        "[HF] Model device:",
        model.device,
    )

    generation_pipeline = pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
        return_full_text=False,
        clean_up_tokenization_spaces=False,
    )

    # The text-generation pipeline creates its own copy of
    # the model's generation config and applies task defaults.
    # Configure that effective copy so greedy decoding does not
    # retain sampling options or the legacy max_length value.
    generation_config = generation_pipeline.generation_config
    generation_config.max_length = None
    generation_config.max_new_tokens = max_new_tokens
    generation_config.do_sample = False
    generation_config.temperature = None
    generation_config.top_p = None
    generation_config.top_k = None

    llm = HuggingFacePipeline(
        pipeline=generation_pipeline,
        model_id=model_id,
    )

    return LocalChatModel(
        llm=llm,
        tokenizer=tokenizer,
        model_name=model_id,
    )
