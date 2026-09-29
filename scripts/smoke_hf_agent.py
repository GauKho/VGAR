from __future__ import annotations

import asyncio

from vgar.agents.core import create_core_agent


async def main() -> None:
    agent = await create_core_agent()

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Use the graph MCP tools to search "
                        "for repository symbols with the "
                        "exact query 'auth'. Report only "
                        "facts returned by tools."
                    ),
                }
            ]
        }
    )

    messages = result.get(
        "messages",
        [],
    )

    for message in messages:
        print(message)


if __name__ == "__main__":
    asyncio.run(main())
