"""Throwaway spike (spec 2026-11-19 §8): load Qwen 4-bit once, run one turn with a tool schema, print speed and memory.

  PYTHONPATH=src ~/.vgar-wsl/bin/python baseline/nav/spike_qwen_speed.py

Go on with T2 if one turn takes about 10 s or less (12 turns per task stays under 2 minutes).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baseline.nav.model import QwenModel, parse_tool_calls
from baseline.nav.tools import FileTools

MESSAGES = [{"role": "system", "content": "You find the code to change for an issue. Use the tools to read the repo."},
            {"role": "user", "content": "Issue: login fails when the username contains '@'. Look at auth/parser.py."}]


def main() -> int:
    import torch

    started = time.perf_counter()
    model = QwenModel()
    print(f"load: {time.perf_counter() - started:.1f} s, gpu {torch.cuda.memory_allocated() / 2**30:.2f} GiB")
    schemas = FileTools(Path(".")).schemas()
    for turn in (1, 2):
        text, usage = model.generate(MESSAGES, schemas, max_new_tokens=256)
        print(f"turn {turn}: {usage['seconds']:.1f} s, prompt {usage['prompt_tokens']} tok, "
              f"completion {usage['completion_tokens']} tok, "
              f"{usage['completion_tokens'] / usage['seconds']:.1f} tok/s")
    print("reply:", text[:400].replace("\n", " "))
    print("tool calls:", parse_tool_calls(text))
    print(f"peak gpu: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
