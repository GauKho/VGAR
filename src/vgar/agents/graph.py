from langchain_core.messages import SystemMessage
from langgraph.graph import (
    END,
    START,
    MessagesState,
    StateGraph,
)
from langgraph.prebuilt import (
    ToolNode,
    tools_condition,
)

from vgar.agents.core import load_mcp_tools, load_system_prompt
from vgar.config.settings import Settings, get_settings
from vgar.models.factory import create_core_model


async def create_agent(settings: Settings | None = None):
    settings = settings or get_settings()

    # 1. Load MCP tools
    tools = await load_mcp_tools(settings)

    # 2. Create core LLM (single factory, driven by Settings)
    model = create_core_model(settings.model)

    # 3. Bind MCP tools to model
    model_with_tools = model.bind_tools(
        tools,
    )
    system_message = SystemMessage(content=load_system_prompt())

    # 4. Model node
    async def call_model(
        state: MessagesState,
    ):
        response = await model_with_tools.ainvoke(
            [system_message, *state["messages"]]
        )

        return {
            "messages": [response],
        }

    # 5. Tool execution node
    tool_node = ToolNode(tools)

    # 6. Build graph
    builder = StateGraph(MessagesState)

    builder.add_node(
        "model",
        call_model,
    )

    builder.add_node(
        "tools",
        tool_node,
    )

    builder.add_edge(
        START,
        "model",
    )

    builder.add_conditional_edges(
        "model",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge(
        "tools",
        "model",
    )

    return builder.compile()
