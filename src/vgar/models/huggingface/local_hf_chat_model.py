# qwen_chat_model.py

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Sequence

from pydantic import Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from langchain_huggingface import HuggingFacePipeline


_TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.DOTALL,
)


class LocalChatModel(BaseChatModel):
    """
    Bridge:
        LangChain messages/tools
            ↕
        Qwen native chat/tool format
    """

    llm: HuggingFacePipeline
    tokenizer: Any
    model_name: str

    bound_tools: list[dict[str, Any]] = Field(
        default_factory=list
    )

    @property
    def _llm_type(self) -> str:
        return "local-transformers"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
        }

    def bind_tools(
        self,
        tools: Sequence[
            dict[str, Any] | type | BaseTool | Any
        ],
        *,
        tool_choice: str | dict | bool | None = None,
        **kwargs: Any,
    ) -> "LocalChatModel":
        """
        create_agent() calls this internally.

        Convert LangChain tools to the function schema
        understood by Qwen's chat template.
        """

        converted_tools = [
            convert_to_openai_tool(tool)
            for tool in tools
        ]

        return self.model_copy(
            update={
                "bound_tools": converted_tools,
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        qwen_messages = self._to_qwen_messages(
            messages
        )

        template_kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }

        if self.bound_tools:
            template_kwargs["tools"] = self.bound_tools

        prompt = self.tokenizer.apply_chat_template(
            qwen_messages,
            **template_kwargs,
        )

        invoke_kwargs: dict[str, Any] = {}

        if stop:
            invoke_kwargs["stop"] = stop

        raw_output = self.llm.invoke(
            prompt,
            **invoke_kwargs,
        )

        message = self._parse_qwen_output(
            raw_output
        )

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=message
                )
            ]
        )

    def _to_qwen_messages(
        self,
        messages: list[BaseMessage],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for message in messages:

            if isinstance(message, SystemMessage):
                result.append({
                    "role": "system",
                    "content": self._text(message.content),
                })

            elif isinstance(message, HumanMessage):
                result.append({
                    "role": "user",
                    "content": self._text(message.content),
                })

            elif isinstance(message, AIMessage):
                item: dict[str, Any] = {
                    "role": "assistant",
                    "content": self._text(message.content),
                }

                if message.tool_calls:
                    item["tool_calls"] = [
                        {
                            "name": call["name"],
                            "arguments": call["args"],
                        }
                        for call in message.tool_calls
                    ]

                result.append(item)

            elif isinstance(message, ToolMessage):
                result.append({
                    "role": "tool",
                    "content": self._text(message.content),
                })

            else:
                raise TypeError(
                    "Unsupported message type: "
                    f"{type(message).__name__}"
                )

        return result

    def _parse_qwen_output(
        self,
        raw_output: str,
    ) -> AIMessage:
        raw_output = raw_output.replace(
            "<|im_end|>",
            "",
        ).strip()

        matches = _TOOL_CALL_PATTERN.findall(
            raw_output
        )

        tool_calls: list[dict[str, Any]] = []

        for block in matches:
            parsed = json.loads(
                block.strip()
            )

            name = parsed["name"]
            arguments = parsed.get(
                "arguments",
                {},
            )

            if not isinstance(arguments, dict):
                raise ValueError(
                    "Tool arguments must be an object."
                )

            tool_calls.append({
                "name": name,
                "args": arguments,
                "id": f"call_{uuid.uuid4().hex}",
                "type": "tool_call",
            })

        content = _TOOL_CALL_PATTERN.sub(
            "",
            raw_output,
        ).strip()

        return AIMessage(
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content

        return json.dumps(
            content,
            ensure_ascii=False,
        )