"""Child interpreter inventory and import gate; never imports a legacy agent client."""
import json
import os
import sys
from importlib import import_module, metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
FORBIDDEN = ("langchain", "langgraph", "torch", "transformers", "accelerate", "peft", "trl")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    packages = {d.metadata["Name"]: d.version for d in metadata.distributions()}
    bad = sorted(n for n in packages if n.lower().replace("_", "-").startswith(FORBIDDEN))
    if "--require-no-langchain" in sys.argv and bad:
        raise RuntimeError(f"Forbidden runtime distributions: {bad}")
    classes = {}
    for name in ("graph", "repository", "execution", "repair"):
        module = import_module(f"vgar.mcp.servers.{name}_server")
        classes[name] = type(module.mcp).__module__ + "." + type(module.mcp).__name__
        sdk_class = import_module("mcp.server").MCPServer if int(metadata.version("mcp").split(".")[0]) == 2 else import_module("mcp.server.fastmcp").FastMCP
        require(isinstance(module.mcp, sdk_class), "Incorrect SDK server inheritance")
    from vgar.mcp import registry
    from vgar.mcp.proposal.tools import CORE_TOOLS
    require(len(registry.PUBLIC_TOOLS) == 20 and CORE_TOOLS <= registry.PUBLIC_TOOLS, "Core registry incomplete")
    require("vgar.mcp.client" not in sys.modules, "Legacy client eagerly imported")
    bad_imports = sorted(n for n in sys.modules if n.split(".")[0].startswith(FORBIDDEN))
    require(not bad_imports, f"Forbidden runtime imports: {bad_imports}")
    major = int(metadata.version("mcp").split(".")[0])
    require(all(value.endswith(".ResourceServer" if name == "graph" else ".MCPServer" if major == 2 else ".FastMCP")
                for name, value in classes.items()), "Incorrect server class")
    print(json.dumps({"status": "PASS", "python": sys.executable, "sdk": metadata.version("mcp"),
                      "classes": classes, "packages": packages, "forbidden_packages": bad,
                      "forbidden_imports": bad_imports, "client_imported": False,
                      "graph_backend": os.environ.get("VGAR_GRAPH_BACKEND")}))


if __name__ == "__main__":
    main()
