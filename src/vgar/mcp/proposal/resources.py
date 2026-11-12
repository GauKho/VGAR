"""Raw-URI resource adapter. No SDK decoding, graph algorithm, or arbitrary file access."""
from __future__ import annotations

import json
import re
from contextlib import nullcontext
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from vgar.contracts.error import GraphError
from vgar.mcp.schemas import error_from_exception
from vgar.mcp.tooling import audit_resource

from . import contracts as c
from .context import check_context, check_source, current_context, request_scope
from .security import read_audit, sanitize, scrub_secrets

CANONICAL_RESOURCES = (
    "vgar://repo/summary", "vgar://repo/schema", "vgar://graph/node/{node_id}",
    "vgar://graph/subgraph/{node_id}?k=2", "vgar://component/{component_id}", "vgar://task/{task_id}",
    "vgar://evidence/baseline", "vgar://audit/log",
)
LEGACY_ALIASES = ("vgar://graph/subgraph/{node_id}",)
_RESOURCE_URIS = dict(zip(("summary", "schema", "node", "subgraph", "component", "task", "baseline", "audit"), CANONICAL_RESOURCES, strict=True))
_STATIC = {"vgar://repo/summary": "summary", "vgar://repo/schema": "schema",
           "vgar://evidence/baseline": "baseline", "vgar://audit/log": "audit"}
_PREFIXES = {"vgar://graph/node/": "node", "vgar://graph/subgraph/": "subgraph",
             "vgar://component/": "component", "vgar://task/": "task"}
_CONTROL_FIELDS = {"env", "environ", "environment", "session", "run_record", "generation", "gold_patch",
                   "test_patch", "oracle", "fail_to_pass", "pass_to_pass", "private_key", "system_prompt"}


class ResourceBoundaryError(GraphError, ValueError):
    """Pre-sanitized error survives the worker/request context unwinding."""

    def __init__(self, exc, ctx):
        public = error_from_exception(exc)
        self.code = public.code
        super().__init__(scrub_secrets(public.message, ctx.secrets),
                         details=sanitize(public.details, secret_values=ctx.secrets))


def parse_resource_uri(uri: str) -> c.ResourceRequest:
    if not isinstance(uri, str) or not uri or len(uri) > 2048 or any(ord(ch) < 32 for ch in uri):
        raise ValueError("Invalid or oversized resource URI")
    if "#" in uri or re.search(r"%(?![0-9a-fA-F]{2})", uri):
        raise ValueError("Invalid resource encoding/fragment")
    parts = urlsplit(uri)
    if parts.scheme != "vgar" or "@" in parts.netloc or "\\" in uri:
        raise ValueError("Unsupported resource URI")
    base, separator, query = uri.partition("?")
    kind, identifier = _STATIC.get(base), None
    if kind is None:
        for prefix, candidate in _PREFIXES.items():
            if base.startswith(prefix):
                encoded = base[len(prefix):]
                if not encoded:
                    raise ValueError("Empty resource ID")
                identifier = unquote(encoded, encoding="utf-8", errors="strict")
                if not identifier or len(identifier) > 2048 or any(ord(ch) < 32 for ch in identifier):
                    raise ValueError("Invalid resource ID")
                kind = candidate
                break
    if kind is None:
        raise ValueError("Unknown resource URI")
    cursor = 0
    if separator:
        if kind == "subgraph" and query == "k=2":
            pass
        elif kind == "audit" and re.fullmatch(r"cursor=[0-9]{1,20}", query):
            cursor = int(query[7:])
        else:
            raise ValueError("Unsupported or duplicate resource query")
    return c.ResourceRequest(uri=uri, kind=kind, resource_id=identifier, cursor=cursor,
                             k=2 if kind == "subgraph" else None,
                             legacy=kind in {"summary", "node"} or kind == "subgraph" and not separator)


def _json_object(raw):
    def finite(value):
        raise ValueError("Non-finite JSON value: " + value)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    value = json.loads(raw, parse_constant=finite, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Resource payload must be a JSON object")  # noqa: TRY004 - boundary maps validation to INVALID_ARGUMENT
    return value


def _public(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.casefold() in _CONTROL_FIELDS else _public(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public(item) for item in value]
    return value


def encode_resource(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


_GRAPH_KINDS = frozenset({"schema", "component", "task", "baseline"})


class ResourceReader:
    def __init__(self, tools, service, audit):
        self.tools, self.service, self.audit = tools, service, audit

    def read(self, uri, *, context=None):
        ctx = current_context() if context is None else context
        label = uri[:2048].encode("utf-8", errors="replace").decode("utf-8") if isinstance(uri, str) else type(uri).__name__
        kwargs = {"server": "graph", "resource": "invalid-resource:" + c.digest(label), "backend": self.service.backend_name,
                  "audit": self.audit}
        try:
            request = parse_resource_uri(uri)
            kwargs["resource"] = LEGACY_ALIASES[0] if request.kind == "subgraph" and request.legacy else _RESOURCE_URIS[request.kind]
            if ctx is None and self.tools.context_factory is not None:
                ctx = self.tools._context("resource_read", request)
            if ctx is not None:
                check_source(ctx)
            elif not request.legacy and not self._served_by_graph(request):
                raise ValueError("Host-bound context required for new resources")
        except BaseException as exc:
            trusted = None
            try:
                if ctx is not None:
                    trusted = check_context(ctx)
            except (ValueError, OSError):
                pass  # Denial is still audited without using unverified model context.
            with request_scope(trusted) if trusted is not None else nullcontext(), audit_resource(**kwargs):
                if trusted is not None and isinstance(exc, Exception):
                    raise ResourceBoundaryError(exc, trusted) from None
                raise
        with request_scope(ctx) if ctx is not None else nullcontext(), audit_resource(**kwargs):
            try:
                return self._content(request, ctx)
            except Exception as exc:  # Sanitize before request scope/thread unwinds, then re-raise.
                if ctx is not None:
                    raise ResourceBoundaryError(exc, ctx) from None
                raise

    def _content(self, request, ctx):
        cap = min(65536, ctx.limits.read_bytes) if ctx else 65536
        if request.legacy or request.kind == "subgraph":
            raw = self._legacy(request, ctx)
            if ctx:
                raw = scrub_secrets(raw, ctx.secrets)
        elif request.kind == "audit":
            cap = min(262144, ctx.limits.audit_bytes)
            raw = encode_resource(read_audit(ctx, request.cursor, output_bytes=cap))
        elif self._served_by_graph(request):
            raw = self._graph_resource(request, ctx)
        else:
            raw = self._provider(request, ctx, cap)
        if len(raw.encode("utf-8")) > cap:
            raise ValueError("Resource exceeds configured UTF-8 byte limit")
        _json_object(raw)
        if ctx:
            check_source(ctx)
        return raw

    def _served_by_graph(self, request):
        """Schema/component/task/baseline come from the graph service when the host registered no provider."""
        return request.kind in _GRAPH_KINDS and self.tools.registry.get("resource_" + request.kind) is None

    def _graph_resource(self, request, ctx):
        if request.kind == "task" and ctx is not None and request.resource_id != ctx.task_id:
            raise ValueError("Cross-task resource access refused")
        if request.kind == "schema":
            value = self.service.get_schema()
        elif request.kind == "component":
            value = self.service.get_component(request.resource_id)
        elif request.kind == "task":
            value = self.service.get_task(request.resource_id)
        else:
            value = self.service.get_baseline()
        raw = encode_resource(value)
        return scrub_secrets(raw, ctx.secrets) if ctx else raw

    def _legacy(self, request, ctx):
        def validate():
            if ctx:
                check_source(ctx)
                store = getattr(self.service, "store", None)
                if store is not None and store.requested_graph_version != ctx.snapshot_hash:
                    raise ValueError("Bound resource store must pin snapshot, not latest")
                if self.service.get_repository_summary().graph_version != ctx.snapshot_hash:
                    raise ValueError("Resource backend snapshot does not match host binding")
        validate()
        if request.kind == "summary":
            result = self.service.get_repository_summary()
        elif request.kind == "node":
            result = self.service.get_node(request.resource_id)
        else:
            if ctx and self.tools.limits.max_hops < 2:
                raise ValueError("Depth 2 exceeds host resource hop limit")
            limit = min(200, self.tools.limits.max_nodes)
            result = self.service.get_subgraph(request.resource_id, depth=2, limit=limit)
            if len(result.nodes) > limit or result.depth != 2:
                raise ValueError("Subgraph provider exceeded resource bounds")
        validate()
        return result.model_dump_json(indent=2)

    def _provider(self, request, ctx, cap):
        if request.kind == "task" and request.resource_id != ctx.task_id:
            raise ValueError("Cross-task resource access refused")
        provider = self.tools._required("resource_" + request.kind, ctx)
        value = provider.snapshot_resource(request, ctx)
        try:
            result = self.tools._result(c.ResourceResult, value, ctx)
        except ValidationError:
            raise ValueError("Resource provider output failed validation") from None
        if result.resource_kind != request.kind or result.resource_id != request.resource_id:
            raise ValueError("Resource kind/ID binding mismatch")
        if result.availability == "UNAVAILABLE":
            raise GraphError("Resource unavailable", details={"reason": "RESOURCE_UNAVAILABLE", "kind": request.kind})
        if result.availability == "PARTIAL" and not result.reasons:
            raise ValueError("Partial resource requires reasons")
        if len(result.payload_json.encode("utf-8")) > cap:
            raise ValueError("Provider resource exceeds byte limit")
        payload = _json_object(result.payload_json)
        if not payload:
            raise ValueError("Empty provider resource is not availability evidence")
        for key in c.SnapshotBinding.model_fields:
            if key in payload and payload[key] != getattr(ctx, key):
                raise ValueError("Resource payload identity binding mismatch")
        if request.kind == "baseline" and not result.evidence:
            raise ValueError("Baseline requires persisted evidence references")
        if "_resource" in payload:
            raise ValueError("Reserved resource metadata field")
        metadata = {"binding": result.binding.model_dump(), "availability": result.availability,
                    "reasons": result.reasons, "evidence": [ref.model_dump() for ref in result.evidence]}
        data = sanitize(_public({**payload, "_resource": metadata}), secret_values=ctx.secrets)
        if data["_resource"]["binding"] != metadata["binding"] or data["_resource"]["evidence"] != metadata["evidence"]:
            raise ValueError("Sensitive resource identity/reference cannot be published")
        return encode_resource(data)
