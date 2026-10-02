"""
VGAR-MCP
Verified Graph-Augmented Reasoning via Model Context Protocol.
"""

from vgar.config.settings import load_env

# .env must be in os.environ before transformers / huggingface_hub are imported
# and in every MCP server process (python -m vgar.mcp.servers.*).
load_env()

__version__ = "0.1.0"
