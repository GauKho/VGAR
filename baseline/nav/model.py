"""Qwen for T2 (spec 2026-11-19 §8): 4-bit nf4 on the GPU, greedy, tool calls as ``<tool_call>`` JSON blocks."""
from __future__ import annotations

import json
import re
import time
from typing import Any

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
_TOOL_CALL = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
_FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_END_MARKERS = ("<|im_end|>", "<|endoftext|>")


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Every ``<tool_call>`` block as ``{"name", "arguments"}``; an unreadable block as ``{"error"}``."""
    calls = []
    for block in _TOOL_CALL.findall(text):
        try:
            data = json.loads(block)
            calls.append({"name": str(data["name"]), "arguments": dict(data.get("arguments") or {})})
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            calls.append({"error": f"{type(error).__name__}: {error}"})
    return calls


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value] if isinstance(value, list) else []


MAX_ANSWER_ITEMS = 20   # files and functions each, so recall is defined up to @20


def _answer(data: Any) -> dict[str, list[str]] | None:
    if isinstance(data, dict) and ("files" in data or "functions" in data):
        return {"files": _as_list(data.get("files"))[:MAX_ANSWER_ITEMS],
                "functions": _as_list(data.get("functions"))[:MAX_ANSWER_ITEMS]}
    return None


def parse_final(text: str) -> dict[str, list[str]] | None:
    """The answer JSON ``{"files": [<=20], "functions": [<=20]}`` outside tool calls, or None."""
    text = _TOOL_CALL.sub("", text)
    candidates = _FENCED.findall(text)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            found = _answer(json.loads(candidate))
        except json.JSONDecodeError:
            continue
        if found:
            return found
    # Braces in the prose around the answer break the span above: decode from each "{", the last one first.
    decoder = json.JSONDecoder()
    for index in (i for i in range(len(text) - 1, -1, -1) if text[i] == "{"):
        try:
            found = _answer(decoder.raw_decode(text, index)[0])
        except json.JSONDecodeError:
            continue
        if found:
            return found
    return None


class QwenModel:
    """Qwen loaded once in 4-bit; ``generate`` is greedy."""

    def __init__(self, model_id: str = MODEL_ID, revision: str | None = None) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.model_id, self.revision = model_id, revision
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, quantization_config=quant,
                                                          device_map="cuda")
        self.model.eval()

    def _prompt(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        return self.tokenizer.apply_chat_template(messages, tools=tools or None, add_generation_prompt=True,
                                                  tokenize=False)

    def prompt_tokens(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> int:
        return len(self.tokenizer(self._prompt(messages, tools))["input_ids"])

    def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                 max_new_tokens: int = 1536) -> tuple[str, dict[str, Any]]:
        # 1536: the longest final turn seen (783 tokens) plus a full 20-file, 20-function answer still fits
        import torch

        started = time.perf_counter()
        inputs = self.tokenizer(self._prompt(messages, tools), return_tensors="pt").to("cuda")
        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new = output[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(new, skip_special_tokens=False)   # keep <tool_call> markers
        for marker in _END_MARKERS:
            text = text.replace(marker, "")
        return text.strip(), {"prompt_tokens": int(inputs["input_ids"].shape[1]), "completion_tokens": len(new),
                              "seconds": time.perf_counter() - started}
