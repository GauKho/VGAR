from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import BaseTool

from vgar.config.settings import Settings, get_settings
from vgar.mcp import create_mcp_client
from vgar.models.factory import create_core_model


PROMPT_PATH = (
    Path(__file__).parent
    / "prompts"
    / "system.md"
)


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(
        encoding="utf-8"
    )


async def load_mcp_tools(settings: Settings | None = None) -> list[BaseTool]:
    client = create_mcp_client(settings)

    tools = await client.get_tools()

    if not tools:
        raise RuntimeError(
            "MCP returned no tools."
        )

    return tools


async def create_core_agent(settings: Settings | None = None):
    settings = settings or get_settings()

    tools = await load_mcp_tools(settings)

    model = create_core_model(settings.model)

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=load_system_prompt(),
    )

    return agent
