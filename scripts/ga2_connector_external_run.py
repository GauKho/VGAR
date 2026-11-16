"""GA-2 real run: build each repo and print Connector/ExternalSystem counts and examples."""
import json
import sys
import time
from collections import Counter
from pathlib import Path

from vgar.contracts.schema import validate_graph_document
from vgar.graph.builder import PythonGraphBuilder

out = {}
for arg in sys.argv[1:]:
    root = Path(arg)
    start = time.perf_counter()
    document = PythonGraphBuilder(repo_key=f"run/{root.name}", repository_revision="ga2").build(root)
    validate_graph_document(document)
    seconds = round(time.perf_counter() - start, 1)
    nodes = {node["id"]: node for node in document["nodes"]}
    systems = sorted(node["name"] for node in nodes.values() if node["type"] == "ExternalSystem")
    connectors = sorted((node["qualified_name"], node["properties"]["libraries"], node["properties"]["call_count"])
                        for node in nodes.values() if node["type"] == "Connector")
    edges = Counter((e["type"], nodes[e["source_id"]]["type"], nodes[e["target_id"]]["type"]) for e in document["edges"]
                    if e["type"] in {"DEPENDS_ON", "COMMUNICATES_WITH"})
    out[root.name] = {"seconds": seconds, "arch": {k: document["statistics"]["arch"][k] for k in
                      ("mode", "component_count", "external_system_count", "connector_count")},
                      "external_systems": systems, "connectors": connectors,
                      "edges": {" ".join(k): v for k, v in sorted(edges.items())}}
print(json.dumps(out, indent=1, ensure_ascii=False))
