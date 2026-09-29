from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "configs"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in config: {path}")

    return data


@dataclass(frozen=True)
class AgentSettings:
    max_iterations: int = 5
    max_tool_calls: int = 30
    recursion_limit: int = 50


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    model_id: str
    temperature: float
    max_new_tokens: int
    device: str
    torch_dtype: str
    trust_remote_code: bool


def load_agent_settings() -> AgentSettings:
    config = _load_yaml(CONFIG_DIR / "agent.yaml")

    agent = config.get("agent", {})
    workflow = config.get("workflow", {})

    return AgentSettings(
        max_iterations=int(agent.get("max_iterations", 5)),
        max_tool_calls=int(agent.get("max_tool_calls", 30)),
        recursion_limit=int(workflow.get("recursion_limit", 50)),
    )


def load_model_settings() -> ModelSettings:
    config = _load_yaml(CONFIG_DIR / "model.yaml")

    model = config.get("model", {})
    generation = config.get("generation", {})
    runtime = config.get("runtime", {})

    return ModelSettings(
        provider=str(config.get("provider", "huggingface")),
        model_id=str(model["model_id"]),
        temperature=float(generation.get("temperature", 0.0)),
        max_new_tokens=int(
            generation.get("max_new_tokens", 2048)
        ),
        device=str(runtime.get("device", "auto")),
        torch_dtype=str(runtime.get("torch_dtype", "auto")),
        trust_remote_code=bool(
            runtime.get("trust_remote_code", True)
        ),
    )


def load_mcp_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "mcp.yaml")