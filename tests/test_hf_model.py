from types import SimpleNamespace

from transformers import GenerationConfig

from vgar.models.huggingface import hf_model


def test_local_chat_model_uses_one_greedy_generation_config(
    monkeypatch,
):
    pipeline_arguments = {}
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
    def fake_pipeline(**kwargs):
        pipeline_arguments.update(kwargs)
        return generation_pipeline

    monkeypatch.setattr(hf_model, "pipeline", fake_pipeline)
    chat_model = hf_model.create_local_chat_model(
        max_new_tokens=128,
    )

    construction_config = pipeline_arguments[
        "generation_config"
    ]
    assert construction_config.max_new_tokens == 128
    assert construction_config.max_length is None
    assert construction_config.do_sample is False
    assert construction_config.temperature == 1.0
    assert construction_config.top_p == 1.0
    assert construction_config.top_k == 50

    config = chat_model.llm.pipeline.generation_config
    assert config.max_new_tokens == 128
    assert config.max_length is None
    assert config.do_sample is False
    assert config.temperature == 1.0
    assert config.top_p == 1.0
    assert config.top_k == 50

    assert model.generation_config.max_new_tokens == 128
    assert model.generation_config.max_length is None
    assert model.generation_config.do_sample is False
    assert model.generation_config.temperature == 1.0
    assert model.generation_config.top_p == 1.0
    assert model.generation_config.top_k == 50
