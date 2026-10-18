"""Option B of `vgar solve --agent`: generate the V11 diff with the agent's own in-process model.

Same settings as the M2 worker: the pinned snapshot and revision, the prompt bytes the server
rendered (checked by hash), greedy decoding and output_cap new tokens.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import time

from vgar.repair.contracts import ModelProfile


def load_pinned_agent_model(profile: ModelProfile, max_new_tokens: int):
    """The agent model loaded from the pinned profile snapshot (both --generator values use it)."""
    import torch
    from vgar.models.huggingface.hf_model import create_local_chat_model
    return create_local_chat_model(model_id=str(profile.snapshot), revision=profile.revision, local_files_only=True,
                                   max_new_tokens=max_new_tokens, device_map=profile.device_map,
                                   torch_dtype=getattr(torch, profile.dtype))


class AgentModelGenerator:
    """Generator for run_generation backed by a loaded LocalChatModel.

    timeout_seconds is not enforced: generation runs in this process, unlike the M2 worker.
    """
    mode = "real"
    generator_path = "agent_model"

    def __init__(self, model, profile, policy):
        revision = getattr(model, "revision", None)
        if revision != profile.revision:
            raise ValueError(f"Agent model revision {revision} does not match pinned {profile.revision}")
        self.model, self.profile, self.policy = model, profile, policy

    def generate(self, prompt, profile, timeout_seconds):  # noqa: ARG002
        from vgar.models.huggingface.hf_backend import generation_kwargs
        tokenizer = self.model.tokenizer
        rendered = tokenizer.apply_chat_template(prompt.messages, tokenize=False, add_generation_prompt=True)
        if "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest() != prompt.prompt_hash:
            return {"status": "ERROR", "mode": "real", "reason": "Agent model prompt bytes differ",
                    "truncated": False, "raw_text": ""}
        import torch
        hf = self.model.llm.pipeline.model
        inputs = tokenizer.apply_chat_template(prompt.messages, tokenize=True, add_generation_prompt=True,
                                               return_tensors="pt").to(hf.device)
        settings = deepcopy(hf.generation_config)
        settings.do_sample, settings.max_length = False, None
        settings.temperature, settings.top_p, settings.top_k = 1.0, 1.0, 50
        start = time.monotonic()
        with torch.inference_mode():
            output = hf.generate(inputs, generation_config=settings, **generation_kwargs(self.policy.output_cap))
        generated = output[0, inputs.shape[-1]:].tolist()
        eos = settings.eos_token_id
        eos = [eos] if isinstance(eos, int) else eos or []
        truncated = len(generated) >= self.policy.output_cap and (not generated or generated[-1] not in eos)
        return {"status": "PASS", "mode": "real", "generator_path": self.generator_path,
                "raw_text": tokenizer.decode(generated, skip_special_tokens=True),
                "finish_reason": "length" if truncated else "eos", "truncated": truncated,
                "input_tokens": inputs.shape[-1], "output_tokens": len(generated),
                "model_id": self.profile.model_id, "revision": self.profile.revision,
                "generation_ms": round((time.monotonic() - start) * 1000)}
