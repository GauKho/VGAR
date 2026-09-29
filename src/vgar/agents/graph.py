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

from src.config.settings import get_settings
from src.mcp.client import create_mcp_client
from src.models.huggingface import create_huggingface_model


async def create_agent():
    settings = get_settings()

    # 1. Load MCP tools
    client = create_mcp_client()

    tools = await client.get_tools()

    # 2. Create core LLM
    model = create_huggingface_model(
        settings,
    )

    # 3. Bind MCP tools to model
    model_with_tools = model.bind_tools(
        tools,
    )

    # 4. Model node
    async def call_model(
        state: MessagesState,
    ):
        response = await model_with_tools.ainvoke(
            state["messages"]
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