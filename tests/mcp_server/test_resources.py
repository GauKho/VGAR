"""Resource acceptance: handwritten URI oracle, bounded reads, no production fake data."""
import ast
import importlib.util
import json
from urllib.parse import quote

import pytest

from vgar.contracts.error import GraphError


def test_resource_module_exists():
    assert importlib.util.find_spec("vgar.mcp.proposal.resources")


@pytest.fixture
def reader(bound, tmp_path):
    from graph_fixture import fixture_service
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.resources import ResourceReader
    from vgar.mcp.proposal.tools import CoreTools
    authority, ctx = bound
    audit = AuditLogger(ctx.output_root / "audit.jsonl")
    return ResourceReader(CoreTools(ProviderRegistry()), fixture_service(tmp_path / "graph"), audit), authority, ctx


@pytest.mark.parametrize("raw,kind,identifier", [
    ("vgar://repo/summary", "summary", None),
    ("vgar://repo/schema", "schema", None),
    ("vgar://graph/node/a%2Fb%3Ac", "node", "a/b:c"),
    ("vgar://graph/node/a%252Fb", "node", "a%2Fb"),
    ("vgar://graph/node/" + quote("hàm/π:名", safe=""), "node", "hàm/π:名"),
    ("vgar://graph/subgraph/a%2Fb?k=2", "subgraph", "a/b"),
    ("vgar://graph/subgraph/a%2Fb", "subgraph", "a/b"),
    ("vgar://component/C%3Aport", "component", "C:port"),
    ("vgar://task/task", "task", "task"),
    ("vgar://evidence/baseline", "baseline", None),
    ("vgar://audit/log?cursor=123", "audit", None),
])
def test_uri_oracle(raw, kind, identifier):
    from vgar.mcp.proposal.resources import parse_resource_uri
    request = parse_resource_uri(raw)
    assert request.kind == kind and request.resource_id == identifier
    if kind == "audit": assert request.cursor == 123


@pytest.mark.parametrize("raw", [
    "file:///secret", "vgar://repo/summary?x=1", "vgar://repo/summary#x", "vgar://repo/schema?",
    "vgar://graph/subgraph/a?k=3", "vgar://graph/subgraph/a?k=2&k=2", "vgar://graph/subgraph/a?k=2&x=1",
    "vgar://graph/node/%XX", "vgar://graph/node/%FF", "vgar://graph/node/%00", "vgar://task/",
    "vgar://audit/log?cursor=-1", "vgar://audit/log?cursor=true", "vgar://audit/log?cursor=0&cursor=1",
    "vgar://audit/log?run_id=other", "vgar://repo/schema/extra", "vgar://user@repo/summary",
])
def test_uri_rejects_ambiguous_or_unsupported_requests(raw):
    from vgar.mcp.proposal.resources import parse_resource_uri
    with pytest.raises(ValueError): parse_resource_uri(raw)


def test_inventory_is_eight_plus_one_alias():
    from vgar.mcp.proposal.resources import CANONICAL_RESOURCES, LEGACY_ALIASES
    assert len(CANONICAL_RESOURCES) == 8 and len(set(CANONICAL_RESOURCES)) == 8
    assert LEGACY_ALIASES == ("vgar://graph/subgraph/{node_id}",)


def test_graph_registration_has_eight_canonical_and_alias():
    from pathlib import Path
    source = Path(__file__).resolve().parents[2] / "src/vgar/mcp/servers/graph_server.py"
    uris = {ast.literal_eval(d.args[0]) for n in ast.parse(source.read_text(encoding="utf-8")).body
            if isinstance(n, ast.FunctionDef) for d in n.decorator_list
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "resource"}
    assert uris == {"vgar://repo/summary", "vgar://repo/schema", "vgar://graph/node/{node_id}",
                    "vgar://graph/subgraph/{node_id}?k=2", "vgar://graph/subgraph/{node_id}",
                    "vgar://component/{component_id}", "vgar://task/{task_id}",
                    "vgar://evidence/baseline", "vgar://audit/log"}


def test_legacy_raw_json_and_unknown_node_error(reader):
    from vgar.contracts.error import NodeNotFoundError
    r, _, _ = reader
    expected = r.service.get_repository_summary().model_dump_json(indent=2)
    assert r.read("vgar://repo/summary") == expected
    symbol = r.service.search_symbols("login").symbols[0].symbol_id
    assert r.read("vgar://graph/node/" + quote(symbol, safe="")) == r.service.get_node(symbol).model_dump_json(indent=2)
    assert r.read("vgar://graph/subgraph/" + quote(symbol, safe="")) == r.service.get_subgraph(symbol, depth=2).model_dump_json(indent=2)
    with pytest.raises(NodeNotFoundError): r.read("vgar://graph/node/missing")


@pytest.mark.parametrize("uri", ["vgar://repo/schema", "vgar://component/a", "vgar://task/task", "vgar://evidence/baseline", "vgar://audit/log", "vgar://graph/subgraph/a?k=2"])
def test_untrusted_context_is_always_refused(reader, uri):
    r, _, _ = reader
    with pytest.raises(ValueError): r.read(uri, context={"confirmed": True})


@pytest.mark.parametrize("uri", ["vgar://audit/log"])
def test_audit_resource_still_needs_trusted_context(reader, uri):
    r, _, _ = reader
    with pytest.raises(ValueError, match="context"): r.read(uri)


def test_graph_resources_are_served_without_context_when_no_provider(reader):
    # Spec §7.2 (guide-style): schema/component/task/baseline come from the real graph service.
    from vgar.contracts.error import GraphNotReadyError, NodeNotFoundError
    r, _, _ = reader
    assert json.loads(r.read("vgar://repo/schema")) == r.service.get_schema()
    assert json.loads(r.read("vgar://evidence/baseline"))["tests"] == "NOT_RUN"
    assert json.loads(r.read("vgar://component/app"))["component"] == "app"
    with pytest.raises(NodeNotFoundError): r.read("vgar://component/a")
    with pytest.raises(GraphNotReadyError): r.read("vgar://task/task")


def resource_provider_reader(ctx, *, kind="component", payload='{"component_id":"a"}', output_binding=None, evidence=(), availability="AVAILABLE"):
    from graph_fixture import fixture_service
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal import contracts as c
    from vgar.mcp.proposal.ports import ProviderBinding, ProviderRegistry
    from vgar.mcp.proposal.resources import ResourceReader
    from vgar.mcp.proposal.tools import CoreTools
    class SyntheticProvider:
        def snapshot_resource(self, request, context):
            return c.ResourceResult(binding=output_binding or c.SnapshotBinding.from_context(context), payload_json=payload,
                availability=availability, evidence=evidence, resource_kind=request.kind, resource_id=request.resource_id)
    record = ProviderBinding(SyntheticProvider(), c.SnapshotBinding.from_context(ctx), frozenset({"resource_" + kind}), synthetic=True)
    return ResourceReader(CoreTools(ProviderRegistry((record,), test_only=True)), fixture_service(ctx.output_root.parent / "graph"),
                          AuditLogger(ctx.output_root / "audit.jsonl"))


@pytest.mark.parametrize("uri", ["vgar://repo/schema", "vgar://component/a", "vgar://task/task", "vgar://evidence/baseline"])
def test_missing_provider_falls_back_to_the_graph_not_to_empty_success(reader, uri):
    # Spec §7.2: without a provider the graph service answers; a missing entity is a coded error, never `{}`.
    from vgar.contracts.error import GraphError
    r, _, ctx = reader
    try:
        payload = json.loads(r.read(uri, context=ctx))
    except GraphError as error:
        assert error.details.get("reason") != "CAPABILITY_UNAVAILABLE"
    else:
        assert payload


def test_provider_json_binding_and_secret_redaction(reader):
    from vgar.mcp.proposal.contracts import SnapshotBinding
    _, _, ctx = reader
    r = resource_provider_reader(ctx, payload='{"component_id":"a","password":"bad","note":"synthetic-unshaped-value"}')
    data = json.loads(r.read("vgar://component/a", context=ctx))
    assert data["component_id"] == "a" and data["password"] == "[REDACTED]"
    assert "synthetic-unshaped-value" not in json.dumps(data)
    stale = SnapshotBinding.from_context(ctx).model_copy(update={"snapshot_hash": "sha256:" + "b" * 64})
    with pytest.raises(ValueError, match="binding"):
        resource_provider_reader(ctx, output_binding=stale).read("vgar://component/a", context=ctx)


def test_task_and_baseline_cannot_cross_scope(reader):
    _, _, ctx = reader
    with pytest.raises(ValueError, match="task"):
        resource_provider_reader(ctx, kind="task").read("vgar://task/other", context=ctx)
    from vgar.mcp.proposal.contracts import SnapshotBinding
    binding = SnapshotBinding.from_context(ctx).model_copy(update={"run_id": "other"})
    with pytest.raises(ValueError):
        resource_provider_reader(ctx, kind="baseline", output_binding=binding).read("vgar://evidence/baseline", context=ctx)


@pytest.mark.parametrize("payload", ['{"x":NaN}', '[]', '{broken', '{"x":"' + "a"*66000 + '"}'],
                         ids=["nonfinite", "not-object", "malformed", "oversized"])
def test_provider_payload_must_be_bounded_valid_json_object(reader, payload):
    _, _, ctx = reader
    with pytest.raises(ValueError): resource_provider_reader(ctx, payload=payload).read("vgar://component/a", context=ctx)


def test_baseline_requires_actual_bound_evidence_file(reader):
    from vgar.mcp.proposal import contracts as c
    _, _, ctx = reader
    (ctx.output_root / "baseline.json").write_text('{"public":true}', encoding="utf-8")
    ref = c.EvidenceRef(path="baseline.json", sha256=c.digest('{"public":true}'))
    r = resource_provider_reader(ctx, kind="baseline", payload='{"public":true}', evidence=(ref,))
    assert json.loads(r.read("vgar://evidence/baseline", context=ctx))["public"] is True
    for bad in (ref.model_copy(update={"path": "../secret"}), ref.model_copy(update={"sha256": c.digest("other")})):
        with pytest.raises((ValueError, OSError)):
            resource_provider_reader(ctx, kind="baseline", evidence=(bad,)).read("vgar://evidence/baseline", context=ctx)
    with pytest.raises(ValueError):
        resource_provider_reader(ctx, kind="baseline").read("vgar://evidence/baseline", context=ctx)


def test_audit_serialized_cap_preserves_cursor_boundaries(bound):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.context import request_scope
    from vgar.mcp.proposal.security import read_audit
    _, ctx = bound
    log = AuditLogger(ctx.output_root / "audit.jsonl")
    with request_scope(ctx):
        for i in range(5): log.write("synthetic", {"i": i, "text": "名" * 50})
    cursor, seen = 0, []
    while True:
        page = read_audit(ctx, cursor, output_bytes=800)
        assert len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()) <= 800
        seen.extend(row["payload"]["i"] for row in page["items"])
        assert page["cursor"] > cursor
        cursor = page["cursor"]
        if not page["truncated"]: break
    assert seen == list(range(5))


def test_audit_read_rejects_other_scope_and_torn_tail(reader):
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.context import request_scope
    r, _, ctx = reader
    log = AuditLogger(ctx.output_root / "audit.jsonl")
    log.write("synthetic", {"run_id": "other", "task_id": ctx.task_id})
    with pytest.raises(ValueError, match="Cross"): r.read("vgar://audit/log", context=ctx)
    log._path.write_bytes(b'{"broken":')
    with request_scope(ctx), pytest.raises(ValueError, match="tail"): r.read("vgar://audit/log")


def test_bound_legacy_snapshot_and_source_fail_closed(reader):
    r, _, ctx = reader
    with pytest.raises(ValueError, match="snapshot"): r.read("vgar://repo/summary", context=ctx)
    (ctx.repo_root / "drift.py").write_text("x=1", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory"): r.read("vgar://repo/schema", context=ctx)


def test_frozen_resource_dtos_and_unavailable_provider(reader):
    from vgar.mcp.proposal import contracts as c
    _, _, ctx = reader
    req = c.ResourceRequest(uri="vgar://repo/schema", kind="schema")
    with pytest.raises(ValueError): req.kind = "component"
    with pytest.raises(ValueError): c.ResourceRequest(uri="vgar://repo/schema", kind="schema", confirmed=True)
    from vgar.contracts.error import GraphError
    with pytest.raises(GraphError):
        resource_provider_reader(ctx, availability="UNAVAILABLE").read("vgar://component/a", context=ctx)


def test_failure_audit_keeps_trusted_correlation_without_secret_uri(reader):
    r, _, ctx = reader
    (ctx.repo_root / "drift.py").write_text("x=1", encoding="utf-8")
    with pytest.raises(ValueError):
        r.read("vgar://component/synthetic-unshaped-value", context=ctx)
    event = json.loads(r.audit._path.read_text(encoding="utf-8").splitlines()[0])
    assert event["payload"]["request_id"] == ctx.request_id
    assert event["payload"]["task_id"] == ctx.task_id
    assert "synthetic-unshaped-value" not in json.dumps(event)


def test_provider_validation_error_does_not_disclose_payload(reader):
    _, _, ctx = reader
    r = resource_provider_reader(ctx)
    provider = r.tools.registry.get("resource_component").provider
    provider.snapshot_resource = lambda req, context: {"payload_json": "sensitiveXYZ"}
    with pytest.raises(ValueError) as error:
        r.read("vgar://component/a", context=ctx)
    assert "sensitiveXYZ" not in str(error.value)


def test_resource_reads_preserve_sqlite_bytes_and_source(bound, tmp_path):
    import hashlib
    import shutil
    from pathlib import Path

    from vgar.graph.sqlite_service import SQLiteGraphService
    from vgar.graph.sqlite_store import SQLiteGraphStore
    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.ports import ProviderRegistry
    from vgar.mcp.proposal.resources import ResourceReader
    from vgar.mcp.proposal.tools import CoreTools
    _, ctx = bound
    database = tmp_path / "copy.db"
    shutil.copy2(Path(__file__).resolve().parents[2] / "artifacts/sample_graph.db", database)
    store = SQLiteGraphStore(database)
    version = store.resolve_graph_version()  # Initialize/migrate only the private copy before the read gate.
    store = SQLiteGraphStore(database, graph_version=version)
    service = SQLiteGraphService(store)
    reader = ResourceReader(CoreTools(ProviderRegistry()), service, AuditLogger(ctx.output_root / "audit.jsonl"))
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    summary = json.loads(reader.read("vgar://repo/summary"))
    assert summary["graph_version"] == version
    symbol = service.search_symbols("login").symbols[0].symbol_id
    reader.read("vgar://graph/node/" + quote(symbol, safe=""))
    reader.read("vgar://graph/subgraph/" + quote(symbol, safe=""))
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert list(ctx.repo_root.iterdir()) == []


@pytest.mark.parametrize("value", [True, 0, -1, 262145, float("inf")])
def test_audit_rejects_invalid_serialized_cap(bound, value):
    from vgar.mcp.proposal.security import read_audit
    _, ctx = bound
    with pytest.raises(ValueError): read_audit(ctx, output_bytes=value)


def test_audit_resource_marks_snapshot_mismatch_and_oversized_record(reader):
    from vgar.mcp.audit import AuditLogger
    r, _, ctx = reader
    logger = AuditLogger(ctx.output_root / "audit.jsonl")
    logger.write("synthetic", {"run_id": ctx.run_id, "task_id": ctx.task_id, "snapshot_hash": "other"})
    with pytest.raises(ValueError, match="snapshot"): r.read("vgar://audit/log", context=ctx)
    logger._path.write_bytes(b"x"*65536+b"\n")
    with pytest.raises(ValueError, match="oversized"): r.read("vgar://audit/log", context=ctx)


def test_completed_resource_metadata_is_redacted(reader):
    from vgar.mcp.proposal import contracts as c
    _, _, ctx = reader
    r = resource_provider_reader(ctx, availability="PARTIAL")
    provider = r.tools.registry.get("resource_component").provider
    provider.snapshot_resource = lambda req, context: c.ResourceResult(binding=c.SnapshotBinding.from_context(context),
        resource_kind=req.kind, resource_id=req.resource_id, payload_json='{"component_id":"a"}',
        availability="PARTIAL", reasons=(ctx.secrets[0],))
    raw = r.read("vgar://component/a", context=ctx)
    assert ctx.secrets[0] not in raw
    assert json.loads(raw)["_resource"]["binding"] == c.SnapshotBinding.from_context(ctx).model_dump()


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, GraphError])
def test_provider_errors_do_not_leak_bound_secrets_after_scope_exit(reader, error_type):
    _, _, ctx = reader
    r = resource_provider_reader(ctx)
    provider = r.tools.registry.get("resource_component").provider
    def fail(req, context): raise error_type("synthetic-unshaped-value")
    provider.snapshot_resource = fail
    with pytest.raises(Exception) as error:
        r.read("vgar://component/a", context=ctx)
    from vgar.mcp.schemas import error_from_exception
    public = error_from_exception(error.value).model_dump_json()
    assert ctx.secrets[0] not in public


def test_resource_audit_hard_record_cap_even_if_host_limit_is_higher(reader):
    from dataclasses import replace

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.proposal.context import SecurityLimits, request_scope
    r, authority, ctx = reader
    ctx = authority._sign(replace(ctx, limits=SecurityLimits(audit_records=300)))
    log = AuditLogger(ctx.output_root / "audit.jsonl")
    with request_scope(ctx):
        for i in range(220): log.write("synthetic", {"i": i})
    page = json.loads(r.read("vgar://audit/log", context=ctx))
    assert len(page["items"]) == 200 and page["truncated"]


def test_evidence_reference_containing_secret_is_not_published(reader):
    from vgar.mcp.proposal import contracts as c
    _, _, ctx = reader
    filename = ctx.secrets[0] + ".json"
    (ctx.output_root / filename).write_text('{"public":true}', encoding="utf-8")
    ref = c.EvidenceRef(path=filename, sha256=c.digest('{"public":true}'))
    r = resource_provider_reader(ctx, kind="baseline", evidence=(ref,))
    with pytest.raises(ValueError) as error:
        r.read("vgar://evidence/baseline", context=ctx)
    assert ctx.secrets[0] not in str(error.value)
