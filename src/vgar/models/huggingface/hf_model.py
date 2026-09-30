from __future__ import annotations

from copy import deepcopy

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

    model_generation_config = model.generation_config
    model_generation_config.max_length = None
    model_generation_config.max_new_tokens = max_new_tokens
    model_generation_config.do_sample = False

    # Transformers 5 fills None values from the model config
    # immediately before generate(). These are the neutral values
    # for greedy decoding and therefore survive that merge without
    # enabling sampling or producing invalid-flag warnings.
    model_generation_config.temperature = 1.0
    model_generation_config.top_p = 1.0
    model_generation_config.top_k = 50

    construction_config = deepcopy(
        model_generation_config
    )

    generation_pipeline = pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
        generation_config=construction_config,
        return_full_text=False,
        clean_up_tokenization_spaces=False,
    )

    # The pipeline owns a private copy, so keep both effective
    # configs aligned.
    generation_config = generation_pipeline.generation_config
    generation_config.max_length = None
    generation_config.max_new_tokens = max_new_tokens
    generation_config.do_sample = False
    generation_config.temperature = 1.0
    generation_config.top_p = 1.0
    generation_config.top_k = 50

    llm = HuggingFacePipeline(
        pipeline=generation_pipeline,
        model_id=model_id,
    )

    return LocalChatModel(
        llm=llm,
        tokenizer=tokenizer,
        model_name=model_id,
    )
