"""--generator agent: the agent's own model generates the V11 diff with the M2 settings."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from vgar.agents.agent_generator import AgentModelGenerator, load_pinned_agent_model

REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
RENDERED = "<|im_start|>user\nfix<|im_end|>\n<|im_start|>assistant\n"
EOS = 2


class FakeTokenizer:
    def __init__(self, rendered=RENDERED):
        self.rendered = rendered

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True, **kwargs):
        if not tokenize:
            return self.rendered
        import torch
        return torch.tensor([[1, 5, 6]])

    def decode(self, ids, skip_special_tokens=True):
        return "diff:" + ",".join(str(i) for i in ids if not (skip_special_tokens and i == EOS))


class FakeHF:
    def __init__(self):
        from transformers import GenerationConfig
        self.calls, self.device = [], "cpu"
        self.generation_config = GenerationConfig(eos_token_id=EOS, do_sample=True, temperature=0.7)

    def generate(self, inputs, generation_config=None, **kwargs):
        import torch
        self.calls.append(dict(kwargs, generation_config=generation_config))
        return torch.cat([inputs, torch.tensor([[7, EOS]])], dim=-1)


def fake_model(revision=REVISION, rendered=RENDERED):
    hf = FakeHF()
    return SimpleNamespace(revision=revision, tokenizer=FakeTokenizer(rendered),
                           llm=SimpleNamespace(pipeline=SimpleNamespace(model=hf))), hf


PROFILE = SimpleNamespace(model_id="Qwen/Qwen3-4B-Instruct-2507", revision=REVISION, approved_prototype=True,
                          snapshot=Path("models/snapshots") / REVISION)
POLICY = SimpleNamespace(output_cap=1536)
PROMPT = SimpleNamespace(messages=[{"role": "user", "content": "fix"}], input_tokens=3,
                         prompt_hash="sha256:" + hashlib.sha256(RENDERED.encode("utf-8")).hexdigest())


def test_rendered_mismatch_returns_error_without_generating():
    model, hf = fake_model(rendered="other")
    result = AgentModelGenerator(model, PROFILE, POLICY).generate(PROMPT, PROFILE, 60)
    assert result["status"] == "ERROR" and result["reason"] == "Agent model prompt bytes differ"
    assert result["raw_text"] == "" and hf.calls == []


def test_revision_mismatch_is_a_clear_error():
    model, _ = fake_model(revision="main")
    with pytest.raises(ValueError, match="does not match pinned"):
        AgentModelGenerator(model, PROFILE, POLICY)


def test_generation_uses_output_cap_and_greedy():
    pytest.importorskip("torch")
    model, hf = fake_model()
    result = AgentModelGenerator(model, PROFILE, POLICY).generate(PROMPT, PROFILE, 60)
    call = hf.calls[0]
    assert call["max_new_tokens"] == 1536 and call["do_sample"] is False
    assert call["generation_config"].do_sample is False and call["generation_config"].max_length is None
    assert result["status"] == "PASS" and result["generator_path"] == "agent_model" and result["mode"] == "real"
    assert result["truncated"] is False and result["finish_reason"] == "eos"
    assert result["raw_text"] == "diff:7" and result["input_tokens"] == 3 and result["output_tokens"] == 2
    assert result["revision"] == REVISION and result["model_id"] == PROFILE.model_id


def test_local_chat_model_loads_a_pinned_revision_offline(monkeypatch):
    from transformers import GenerationConfig
    from vgar.models.huggingface import hf_model
    seen = {}
    tokenizer = SimpleNamespace(chat_template="template")
    hf = SimpleNamespace(generation_config=GenerationConfig(), device="cpu")

    def tokenizer_from_pretrained(model_id, **kwargs):
        seen["tokenizer"] = kwargs
        return tokenizer

    def model_from_pretrained(model_id, **kwargs):
        seen["model"] = kwargs
        return hf

    monkeypatch.setattr(hf_model.AutoTokenizer, "from_pretrained", tokenizer_from_pretrained)
    monkeypatch.setattr(hf_model.AutoModelForCausalLM, "from_pretrained", model_from_pretrained)
    monkeypatch.setattr(hf_model, "pipeline", lambda **kwargs: SimpleNamespace(
        generation_config=GenerationConfig(), model=kwargs["model"], tokenizer=kwargs["tokenizer"]))
    monkeypatch.setattr(hf_model, "HuggingFacePipeline", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(hf_model, "LocalChatModel", lambda **kwargs: SimpleNamespace(**kwargs))
    chat = hf_model.create_local_chat_model(model_id="/snap", revision=REVISION, local_files_only=True)
    assert seen["tokenizer"] == {"revision": REVISION, "local_files_only": True}
    assert seen["model"]["revision"] == REVISION and seen["model"]["local_files_only"] is True
    assert chat.revision == REVISION


@pytest.mark.parametrize("change", [{"approved_prototype": False}, {"snapshot": Path("models/snapshots/main")},
                                    {"model_id": "other/model"}])
def test_unpinned_profile_is_refused_before_loading_or_generating(change, monkeypatch):
    from vgar.models.huggingface import hf_model
    monkeypatch.setattr(hf_model, "create_local_chat_model", lambda **kwargs: pytest.fail("model loaded"))
    profile = SimpleNamespace(**dict(vars(PROFILE), **change))
    with pytest.raises(ValueError, match="pinned"):
        load_pinned_agent_model(profile, 512)
    with pytest.raises(ValueError, match="pinned"):
        AgentModelGenerator(fake_model()[0], profile, POLICY)


def test_local_chat_model_reports_token_usage():
    from langchain_core.messages import HumanMessage
    from vgar.models.huggingface.local_hf_chat_model import LocalChatModel

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return "<|im_start|>user hi<|im_end|>"

        def encode(self, text, add_special_tokens=False):
            return text.split()

    llm = SimpleNamespace(invoke=lambda prompt, **kwargs: 'ok <tool_call>{"name": "x", "arguments": {}}</tool_call>')
    model = LocalChatModel.model_construct(llm=llm, tokenizer=Tokenizer(), model_name="m", bound_tools=[], revision=None)
    message = model._generate([HumanMessage("hi")]).generations[0].message
    assert message.usage_metadata == {"input_tokens": 2, "output_tokens": 5, "total_tokens": 7}
