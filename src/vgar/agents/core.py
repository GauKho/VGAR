from __future__ import annotations

from pathlib import Path

from vgar.observability.phase_logger import emit, phase, new_run_id

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


async def load_mcp_tools(
    settings: Settings | None = None,
    *,
    run_id: str | None = None,
) -> list[BaseTool]:
    run_id = run_id or new_run_id()
    with phase("load_mcp_tools", run_id, {"settings_provided": settings is not None}) as log_output:
        client = create_mcp_client(settings)
        tools = await client.get_tools()

        if not tools:
            raise RuntimeError("MCP returned no tools.")

        log_output({
            "tool_count": len(tools),
            "tool_names": [tool.name for tool in tools],
        })
        return tools


def build_core_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    settings: Settings,
    *,
    run_id: str | None = None,
):
    """Wire model + tools into one agent.

    `agent.max_tool_calls` is a hard cap per agent run (one `ainvoke`): once it
    is reached, further calls are blocked and the run ends with an explanation,
    so independent verification can still judge whatever the agent changed.
    """
    run_id = run_id or new_run_id()
    with phase(
        "build_core_agent",
        run_id,
        {
            "model_type": type(model).__name__,
            "tool_count": len(tools),
            "tool_names": [tool.name for tool in tools],
            "max_tool_calls": settings.agent.max_tool_calls,
        },
    ) as log_output:
        system_prompt = load_system_prompt()
        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=[
                ToolCallLimitMiddleware(
                    run_limit=settings.agent.max_tool_calls,
                    exit_behavior="end",
                ),
            ],
        )
        log_output({
            "agent_type": type(agent).__name__,
            "system_prompt_chars": len(system_prompt),
            "tool_count": len(tools),
        })
        return agent


async def create_core_agent(
    settings: Settings | None = None,
    *,
    run_id: str | None = None,
):
    settings = settings or get_settings()
    run_id = run_id or new_run_id()

    with phase(
        "create_core_agent",
        run_id,
        {
            "model_config_type": type(settings.model).__name__,
            "max_tool_calls": settings.agent.max_tool_calls,
        },
    ) as log_output:
        tools = await load_mcp_tools(settings, run_id=run_id)

        with phase(
            "create_model",
            run_id,
            {"factory": "create_core_model", "model_config_type": type(settings.model).__name__},
        ) as model_output:
            model = create_core_model(settings.model)
            model_output({"model_type": type(model).__name__})

        agent = build_core_agent(model, tools, settings, run_id=run_id)
        log_output({
            "tool_count": len(tools),
            "agent_type": type(agent).__name__,
        })
        return agent
