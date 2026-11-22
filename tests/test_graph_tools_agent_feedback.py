"""Tool answers that coding agents misread in the OpenCode runs on ShopFlow (22/11/2026)."""
from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from tests.graph_fixture import fixture_service
from vgar.contracts.error import InvalidQueryError
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server

SHOP = {
    "shop/__init__.py": "",
    "shop/pricing.py": "def round_vnd(amount):\n    return amount\n",
    "shop/checkout.py": "from shop.pricing import round_vnd\n\n\ndef total(lines):\n    return round_vnd(sum(lines))\n",
}
ISSUE = "total() is wrong: round_vnd drops the cents of a checkout total"


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _shop(tmp_path: Path) -> tuple[SQLiteGraphService, str]:
    root = _write(tmp_path / "repo", SHOP)
    document = PythonGraphBuilder(repo_key="t/agent", repository_revision="rev").build(root)
    store = SQLiteGraphStore(tmp_path / "graph.db")
    store.ingest(document)
    return SQLiteGraphService(store, repository_root=root, count_tokens=len, counter_label="test"), document["graph_version"]


@pytest.fixture
def served_shop(tmp_path, monkeypatch) -> str:
    service, version = _shop(tmp_path)
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(graph_server, "graph_service", service)
    return version


def test_search_symbols_skips_external_modules_that_match_the_query(tmp_path: Path) -> None:
    # `import decimal` adds an external Module node without a repository path; its name matches "decimal".
    repo = _write(tmp_path / "shop", {
        "pkg/__init__.py": "",
        "pkg/money.py": "from decimal import Decimal\n\n\ndef parse_decimal(value):\n    return Decimal(value)\n",
    })
    service = fixture_service(tmp_path / "db", repo)

    result = service.search_symbols("decimal", limit=20)

    assert [(symbol.name, symbol.kind, symbol.path) for symbol in result.symbols] == [
        ("parse_decimal", "function", "pkg/money.py")]


def test_related_context_points_to_the_anchors_when_given_the_issue_node_of_find_task_anchors(tmp_path: Path) -> None:
    # Run 1 passed trace_nodes[0] (the task's Issue node) as an anchor and got a bare NODE_NOT_FOUND.
    service, version = _shop(tmp_path)
    issue_id = service.find_task_anchors(ISSUE, None, graph_version=version, task_id="t")["trace_nodes"][0]["id"]

    with pytest.raises(InvalidQueryError) as error:
        service.get_related_context([issue_id], 2000, graph_version=version, task_id="t", issue_text=ISSUE)

    assert "find_task_anchors" in error.value.message


def test_related_context_without_anchors_and_without_result_says_where_anchors_come_from(served_shop: str) -> None:
    # Run 1 called it five times with anchor_ids=[] and got five empty packs with no explanation.
    response = graph_server.get_related_context(anchor_ids=[], graph_version=served_shop, task_id="t",
                                                budget_tokens=2000, issue_text="please have a look")

    assert response["status"] == "PASS"
    assert response["data"]["context"]["items"] == []
    assert "search_symbols" in response["data"]["diagnostics"]["hint"]


PRICING_FIX = """diff --git a/shop/pricing.py b/shop/pricing.py
--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -1,2 +1,2 @@
 def round_vnd(amount):
-    return amount
+    return round(amount, -3)
"""


def _edit_in_place(tmp_path: Path) -> None:
    (tmp_path / "repo" / "shop" / "pricing.py").write_text("def round_vnd(amount):\n    return round(amount, -3)\n",
                                                           encoding="utf-8")


def test_patch_impact_names_the_file_edited_after_the_build(tmp_path: Path) -> None:
    # Runs 1-2: the agent edited files in place, then got 'Graph source coordinates differ from byte range'.
    service, version = _shop(tmp_path)
    assert service.analyze_patch_impact(PRICING_FIX, graph_version=version)["changed"]   # the diff itself is valid

    _edit_in_place(tmp_path)
    with pytest.raises(ValueError) as error:
        service.analyze_patch_impact(PRICING_FIX, graph_version=version)

    assert "shop/pricing.py" in str(error.value) and "git stash" in str(error.value)


def test_verify_patch_names_the_file_edited_after_the_build(tmp_path: Path) -> None:
    from vgar.repair.patch_evidence import verify_patch
    service, version = _shop(tmp_path)
    assert verify_patch(service, PRICING_FIX, graph_version=version)["status"] == "PASS"

    _edit_in_place(tmp_path)
    result = verify_patch(service, PRICING_FIX, graph_version=version)

    assert result["status"] == "ERROR"
    assert result["reasons"][0].startswith("SOURCE_DIFFERS_FROM_SNAPSHOT") and "shop/pricing.py" in result["reasons"][0]


def test_verify_tool_checks_again_once_the_edits_are_stashed(served_shop: str, tmp_path: Path, monkeypatch) -> None:
    # 22/11 scratch run: after `git stash` the tool returned the cached ERROR of the edited tree.
    monkeypatch.setattr(graph_server, "_verify_cache", {})
    pricing = tmp_path / "repo" / "shop" / "pricing.py"
    original = pricing.read_text(encoding="utf-8")
    _edit_in_place(tmp_path)
    edited = anyio.run(graph_server.verify_patch_graph_constraints, PRICING_FIX)

    pricing.write_text(original, encoding="utf-8")   # what `git stash` does
    stashed = anyio.run(graph_server.verify_patch_graph_constraints, PRICING_FIX)

    assert edited["data"]["status"] == "ERROR"
    assert stashed["data"]["status"] == "PASS"
