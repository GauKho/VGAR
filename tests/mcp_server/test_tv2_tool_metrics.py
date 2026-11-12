"""Per-call tool metrics: tokens in/out, processing time and the format of arguments and results.

The server sees only what crosses a tool (proposal §13.2 context token cost, tool latency, tool calls per task);
model tokens are counted by the host.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from graph_fixture import fixture_service
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server

ROOT = Path(__file__).resolve().parents[2]


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_describe_gives_type_and_size_never_content():
    from vgar.mcp.tool_metrics import describe

    assert describe("SECRET_MARKER") == "str 13B"
    assert describe(3) == "int" and describe(None) == "null" and describe(True) == "bool"
    assert describe([1, 2]) == "list[2]" and describe({"a": 1}) == "dict[1]"


def test_tokens_use_the_pinned_tokenizer_when_configured(monkeypatch):
    from vgar.mcp import tool_metrics

    monkeypatch.delenv("VGAR_TOKENIZER_MANIFEST", raising=False)
    tool_metrics._counter.cache_clear()
    assert tool_metrics.token_count("abcdefgh") == (2, "approx_chars_div_4")

    class Fake:
        counter_label = "local-hf:fake"

        def __call__(self, text):
            return len(text.split())

    monkeypatch.setattr(tool_metrics, "_counter", lambda: Fake())
    assert tool_metrics.token_count("one two three") == (3, "local-hf:fake")


def test_each_tool_call_writes_one_metrics_record(tmp_path, monkeypatch):
    metrics = tmp_path / "metrics.jsonl"
    monkeypatch.setenv("VGAR_MCP_METRICS_LOG", str(metrics))
    monkeypatch.setattr(graph_server, "graph_service", fixture_service(tmp_path / "graph"))
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    response = graph_server.search_symbols("login", limit=5)
    record, = _lines(metrics)
    assert record["tool"] == "search_symbols" and record["server"] == "graph" and record["status"] == "PASS"
    assert record["request_id"] == response["metadata"]["request_id"]
    assert isinstance(record["duration_ms"], int) and record["duration_ms"] >= 0
    assert record["args"] == {"query": "str 5B", "limit": "int"}
    assert record["result"]["data"]["symbols"].startswith("list[")
    assert record["input_tokens"] > 0 and record["output_tokens"] > 0 and record["token_method"]
    assert record["output_bytes"] > 0


def test_metrics_never_contain_diff_content(tmp_path, monkeypatch):
    import asyncio

    metrics = tmp_path / "metrics.jsonl"
    monkeypatch.setenv("VGAR_MCP_METRICS_LOG", str(metrics))
    monkeypatch.setattr(graph_server, "graph_service", fixture_service(tmp_path / "graph"))
    monkeypatch.setattr(graph_server, "_audit_logger", AuditLogger(tmp_path / "audit.jsonl"))
    asyncio.run(graph_server.verify_patch_graph_constraints("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+SECRET_MARKER\n"))
    text = metrics.read_text(encoding="utf-8")
    assert "SECRET_MARKER" not in text and '"diff": "str ' in text


def test_summary_script_tabulates_calls_latency_and_tokens(tmp_path):
    metrics = tmp_path / "metrics.jsonl"
    rows = [{"tool": "search_symbols", "server": "graph", "status": "PASS", "duration_ms": d, "input_tokens": 5,
             "output_tokens": 50, "token_method": "approx_chars_div_4"} for d in (10, 20, 30, 40)]
    rows.append({"tool": "get_callers", "server": "graph", "status": "ERROR", "duration_ms": 7, "input_tokens": 9,
                 "output_tokens": 20, "token_method": "approx_chars_div_4"})
    metrics.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out = tmp_path / "summary"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/summarize_mcp_metrics.py"), "--metrics", str(metrics),
                             "--out", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "mcp_metrics.json").read_text(encoding="utf-8"))
    search = summary["tools"]["search_symbols"]
    assert search["calls"] == 4 and search["errors"] == 0 and search["p50_ms"] == 25.0
    assert search["input_tokens"] == 20 and search["output_tokens"] == 200
    assert summary["tools"]["get_callers"]["errors"] == 1 and summary["total_calls"] == 5
    assert "| search_symbols |" in (out / "mcp_metrics.md").read_text(encoding="utf-8")
