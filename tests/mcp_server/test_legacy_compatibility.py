"""Independent H1 inventory guards; production runtime is tested separately over STDIO."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads((ROOT / "tests/fixtures/mcp_server/expected_contract.json").read_text(encoding="utf-8"))


def test_public_surface_matches_frozen_h1():
    actual, resources, prompts = [], [], []
    for server in ("graph", "repository", "execution"):
        source = (ROOT / f"src/vgar/mcp/servers/{server}_server.py").read_text(encoding="utf-8-sig")
        for node in ast.parse(source).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "mcp":
                    continue
                if dec.func.attr == "tool":
                    actual.append({"server": server, "name": node.name, "signature": ast.unparse(node.args)})
                elif dec.func.attr == "resource":
                    resources.append(ast.literal_eval(dec.args[0]))
                elif dec.func.attr == "prompt":
                    prompts.append(node.name)
    key = lambda row: (row["server"], row["name"])
    legacy_keys = {key(row) for row in ORACLE["legacy_surface"]}
    assert sorted((row for row in actual if key(row) in legacy_keys), key=key) == sorted(ORACLE["legacy_surface"], key=key)
    resource_oracle = json.loads((ROOT / "tests/fixtures/mcp_server/resource_contract.json").read_text(encoding="utf-8"))
    assert set(ORACLE["legacy_resources"]) <= set(resources)
    assert sorted(resources) == sorted(resource_oracle["canonical"] + resource_oracle["legacy_aliases"])
    assert prompts == ["repair_with_graph_context"]


def test_legacy_payload_bytes_and_canonical_unchanged():
    for row in ORACLE["legacy_payloads"].values():
        raw = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        canonical = json.dumps(json.loads(raw), sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(canonical).hexdigest() == row["canonical_sha256"]
