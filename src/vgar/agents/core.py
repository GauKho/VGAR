from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import BaseTool

from vgar.mcp import create_mcp_client
from vgar.models.huggingface.hf_model import create_local_chat_model


PROMPT_PATH = (
    Path(__file__).parent
    / "prompts"
    / "system.md"
)


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(
        encoding="utf-8"
    )


async def load_mcp_tools() -> list[BaseTool]:
    client = create_mcp_client()

    tools = await client.get_tools()

    if not tools:
        raise RuntimeError(
            "MCP returned no tools."
        )

    return tools


async def create_core_agent():
    tools = await load_mcp_tools()

    model = create_local_chat_model()

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=load_system_prompt(),
    )

    return agent