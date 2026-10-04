from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
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


def build_core_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    settings: Settings,
):
    """Wire model + tools into one agent.

    `agent.max_tool_calls` is a hard cap per agent run (one `ainvoke`): once it
    is reached, further calls are blocked and the run ends with an explanation,
    so independent verification can still judge whatever the agent changed.
    """
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=load_system_prompt(),
        middleware=[
            ToolCallLimitMiddleware(
                run_limit=settings.agent.max_tool_calls,
                exit_behavior="end",
            ),
        ],
    )


async def create_core_agent(settings: Settings | None = None):
    settings = settings or get_settings()

    tools = await load_mcp_tools(settings)

    model = create_core_model(settings.model)

    return build_core_agent(model, tools, settings)
