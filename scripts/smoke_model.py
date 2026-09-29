from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage

from vgar.models.huggingface.hf_model import create_local_chat_model


async def main() -> None:
    model = create_local_chat_model()

    response = await model.ainvoke(
        [
            HumanMessage(
                content=(
                    "Reply with exactly: "
                    "VGAR_MODEL_OK"
                )
            )
        ]
    )

    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())