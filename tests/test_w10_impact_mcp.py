"""M3-W10-3: graph MCP tool analyze_patch_impact (envelope, audit, error schema, stdio transport)."""
import asyncio
import json
import shutil
from pathlib import Path

import pytest

from vgar.contracts.impact import ImpactReport
from vgar.graph.builder import PythonGraphBuilder
from vgar.graph.demo_service import DemoGraphService
from vgar.graph.sqlite_service import SQLiteGraphService
from vgar.graph.sqlite_store import SQLiteGraphStore
from vgar.mcp.audit import AuditLogger
from vgar.mcp.servers import graph_server

PATCH = '--- a/pkg/core.py\n+++ b/pkg/core.py\n@@ -11 +11 @@\n-    return x + 1\n+    return x + 2\n'


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    shutil.copytree(Path(__file__).parent / 'fixtures/m1_w10_impact', repo)
    document = PythonGraphBuilder(repo_key='demo/w10', repository_revision='fixture-v1').build(repo)
    store = SQLiteGraphStore(tmp_path / 'graph.db')
    store.ingest(document)
    monkeypatch.setattr(graph_server, 'graph_service', SQLiteGraphService(store, repository_root=repo))
    monkeypatch.setattr(graph_server, '_audit_logger', AuditLogger(tmp_path / 'audit.jsonl'))
    return tmp_path, document['graph_version']


def audit_lines(tmp_path):
    lines = (tmp_path / 'audit.jsonl').read_text(encoding='utf-8').splitlines()
    return [json.loads(line)['payload'] for line in lines]


def test_tool_returns_a_valid_impact_report_and_audits_without_the_diff(snapshot):
    tmp_path, version = snapshot
    result = graph_server.analyze_patch_impact(PATCH, version)
    assert result['status'] == 'PASS' and result['error'] is None
    report = ImpactReport.model_validate_json(json.dumps(result['data']))
    assert len(report.changed) == 1 and report.impacted.status == 'COMPLETE' and len(report.impacted.items) == 8
    entry = audit_lines(tmp_path)[-1]
    assert entry['tool'] == 'analyze_patch_impact' and entry['status'] == 'PASS'
    assert entry['patch_sha256'] == report.patch_hash and entry['changed_count'] == 1 and entry['impacted_count'] == 8
    assert 'return x + 2' not in (tmp_path / 'audit.jsonl').read_text(encoding='utf-8')


def test_tool_passes_limits(snapshot):
    _, version = snapshot
    data = graph_server.analyze_patch_impact(PATCH, version, max_hops=1, max_nodes=3)['data']
    assert data['impacted']['status'] == 'PARTIAL' and data['impacted']['max_hops'] == 1


@pytest.mark.parametrize('diff,version_ok,kwargs,code', [
    ('not a diff', True, {}, 'INVALID_ARGUMENT'),
    (PATCH.replace('pkg/core.py', 'pkg/missing.py'), True, {}, 'INVALID_ARGUMENT'),
    (PATCH, True, {'max_hops': 9}, 'INVALID_ARGUMENT'),
    (PATCH, False, {}, 'GRAPH_NOT_READY')])
def test_tool_errors_follow_the_schema_and_are_audited(snapshot, diff, version_ok, kwargs, code):
    tmp_path, version = snapshot
    result = graph_server.analyze_patch_impact(diff, version if version_ok else 'missing', **kwargs)
    assert result['status'] == 'ERROR' and result['data'] is None and result['error']['code'] == code
    assert audit_lines(tmp_path)[-1]['error_code'] == code


def test_tool_needs_a_repository_root_and_a_snapshot_backend(snapshot, monkeypatch):
    _, version = snapshot
    store = graph_server.graph_service.store
    monkeypatch.setattr(graph_server, 'graph_service', SQLiteGraphService(store))
    assert graph_server.analyze_patch_impact(PATCH, version)['error']['code'] == 'GRAPH_NOT_READY'
    monkeypatch.setattr(graph_server, 'graph_service', DemoGraphService())
    assert graph_server.analyze_patch_impact(PATCH, version)['error']['code'] == 'GRAPH_NOT_READY'


def test_tool_is_listed_over_stdio():
    from vgar.mcp.client import create_mcp_client
    tools = asyncio.run(create_mcp_client(servers=('graph',)).get_tools())
    assert 'graph_analyze_patch_impact' in {t.name for t in tools}
