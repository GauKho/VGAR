"""Create the servers with the official MCP Python SDK 2 (build-server guide: ``from mcp.server import MCPServer``)."""
from __future__ import annotations

import logging

from mcp.server import MCPServer

logger = logging.getLogger(__name__)


def create_server(name: str, *, log_level: str = "WARNING") -> MCPServer:
    """A plain MCPServer, as in the build-server guide.

    Args:
        name: Server name shown to the host.
        log_level: SDK log level.
    """
    logger.debug("server=%s log_level=%s", name, log_level)
    return MCPServer(name, log_level=log_level)


def create_resource_server(name: str, resource_reader, *, log_level: str = "WARNING", prompt_reader=None) -> MCPServer:
    """An MCPServer that reads raw resource URIs and renders prompts through VGAR's readers.

    Args:
        name: Server name shown to the host.
        resource_reader: Function from a raw URI to its text content.
        log_level: SDK log level.
        prompt_reader: Function from a prompt name and its arguments to prompt messages.
    """
    import anyio
    import mcp.types as types
    from mcp.server.lowlevel.helper_types import ReadResourceContents
    from mcp.shared.exceptions import MCPError

    def protocol_error(exc):
        from vgar.mcp.schemas import error_from_exception
        error = error_from_exception(exc)
        code = -32602 if error.code == "INVALID_ARGUMENT" else -32603
        raise MCPError(code, error.message, error.model_dump()) from None

    class ResourceServer(MCPServer):
        async def read_resource(self, uri, *args, **kwargs):
            # Read-only bounded adapter, awaited to completion. Do not abandon a
            # thread on cancellation and pretend its work has stopped.
            try:
                content = await anyio.to_thread.run_sync(resource_reader, str(uri), abandon_on_cancel=False)
            except Exception as exc:  # noqa: BLE001 - translate to the SDK's protocol error, never an envelope
                protocol_error(exc)
            # Match decorators' default MIME and the original legacy wire shape.
            return [ReadResourceContents(content=content, mime_type="text/plain")]

        async def get_prompt(self, name, arguments=None, *args, **kwargs):
            if prompt_reader is None:
                return await super().get_prompt(name, arguments, *args, **kwargs)
            try:
                messages = await anyio.to_thread.run_sync(prompt_reader, name, arguments, abandon_on_cancel=False)
                return types.GetPromptResult(description="VGAR seven-step MCP repair workflow.", messages=messages)
            except Exception as exc:  # noqa: BLE001 - safe boundary before SDK argument validation/name echo
                protocol_error(exc)

    logger.debug("server=%s log_level=%s", name, log_level)
    return ResourceServer(name, log_level=log_level)
