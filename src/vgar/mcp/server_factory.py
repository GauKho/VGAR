"""Select the installed official MCP SDK without importing a legacy client."""
from __future__ import annotations

import logging
from importlib import import_module, metadata
from typing import Any

from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)


def create_server(name: str, *, log_level: str = "WARNING", instructions: str | None = None) -> Any:
    """SDK2 is production; SDK1 remains an explicit compatibility lane.

    A broken SDK import must surface unchanged: falling back would hide a
    partially installed runtime and invalidate its dependency receipt.
    """
    try:
        version = Version(metadata.version("mcp"))
    except (metadata.PackageNotFoundError, InvalidVersion) as exc:
        raise RuntimeError("MCP SDK distribution is missing or has invalid version metadata") from exc
    if version.major == 2:
        cls = import_module("mcp.server").MCPServer
    elif version.major == 1:
        cls = import_module("mcp.server.fastmcp").FastMCP
    else:
        raise RuntimeError(f"Unsupported MCP SDK major: {version.major}")
    logger.debug("server=%s mcp=%s class=%s log_level=%s", name, version, cls.__name__, log_level)
    extra = {"instructions": instructions} if instructions else {}  # sent to the client at initialize
    return cls(name, log_level=log_level, **extra)


def create_resource_server(name: str, resource_reader, *, log_level: str = "WARNING", prompt_reader=None, protocol_reject=None,
                           instructions: str | None = None) -> Any:
    """Route raw URIs before SDK1/SDK2 template decoding, using a public override."""
    import anyio
    from mcp.server.lowlevel.helper_types import ReadResourceContents

    base = type(create_server(name, log_level=log_level))

    def protocol_error(exc):
        from vgar.mcp.schemas import error_from_exception
        error = error_from_exception(exc)
        code = -32602 if error.code == "INVALID_ARGUMENT" else -32603
        if Version(metadata.version("mcp")).major == 2:
            from mcp.shared.exceptions import MCPError
            raise MCPError(code, error.message, error.model_dump()) from None
        from mcp.shared.exceptions import McpError
        from mcp.types import ErrorData
        raise McpError(ErrorData(code=code, message=error.message, data=error.model_dump())) from None

    class ResourceServer(base):
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
                types = import_module("mcp_types" if Version(metadata.version("mcp")).major == 2 else "mcp.types")
                return types.GetPromptResult(description="VGAR seven-step MCP repair workflow.", messages=messages)
            except Exception as exc:  # noqa: BLE001 - safe boundary before SDK argument validation/name echo
                protocol_error(exc)

    server = ResourceServer(name, log_level=log_level, **({"instructions": instructions} if instructions else {}))
    if protocol_reject is not None:
        from vgar.mcp.proposal.prompts import install_protocol_log_guard
        install_protocol_log_guard(protocol_reject)
    return server
