"""Framework-free server package with a lazy legacy client export."""

__all__ = [
    "create_mcp_client",
]


def __getattr__(name: str):
    if name == "create_mcp_client":
        from vgar.mcp.client import create_mcp_client
        return create_mcp_client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
