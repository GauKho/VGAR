from types import SimpleNamespace

from transformers import GenerationConfig

from vgar.models.huggingface import hf_model


def test_local_chat_model_uses_one_greedy_generation_config(
    monkeypatch,
):
    tokenizer = SimpleNamespace(chat_template="template")
    model = SimpleNamespace(
        generation_config=GenerationConfig(
            max_length=20,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
        ),
        device="cpu",
    )
    generation_pipeline = SimpleNamespace(
        generation_config=GenerationConfig(
            max_length=20,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
        )
    )

    monkeypatch.setattr(
        hf_model.AutoTokenizer,
        "from_pretrained",
        lambda _model_id: tokenizer,
    )
    monkeypatch.setattr(
        hf_model.AutoModelForCausalLM,
        "from_pretrained",
        lambda _model_id, **_kwargs: model,
    )
    monkeypatch.setattr(
        hf_model,
        "pipeline",
        lambda **_kwargs: generation_pipeline,
    )
    chat_model = hf_model.create_local_chat_model(
        max_new_tokens=128,
    )

    config = chat_model.llm.pipeline.generation_config
    assert config.max_new_tokens == 128
    assert config.max_length is None
    assert config.do_sample is False
    assert config.temperature is None
    assert config.top_p is None
    assert config.top_k is None
