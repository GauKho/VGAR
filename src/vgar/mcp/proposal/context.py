"""Host-only capability issuance. No JSON/MCP argument can bootstrap an authority."""
import hashlib
import hmac
import json
import math
import os
import re
import secrets as random_secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from uuid import uuid4

from vgar.repair.workspace import inventory

from .locking import lock_key, locked, no_links

_AUTHORITIES = {}
_CANCELLED = set()
_CURRENT = ContextVar("vgar_bound_context", default=None)


@dataclass(frozen=True)
class SecurityLimits:
    read_bytes: int = 65536
    worker_seconds: float = 120
    output_bytes: int = 12000
    lock_seconds: float = 10
    audit_bytes: int = 262144
    audit_records: int = 200

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("Security limits must be finite and positive")
            if name not in {"worker_seconds", "lock_seconds"} and type(value) is not int:
                raise ValueError("Byte/record limits must be integers")


@dataclass(frozen=True)
class WriteGrant:
    grant_id: str
    operation: str
    input_hash: str
    expires_at: float


@dataclass(frozen=True)
class BoundContext:
    authority_id: str
    repo_root: Path
    lease_root: Path
    output_root: Path
    state_root: Path
    request_id: str
    run_id: str
    task_id: str
    snapshot_hash: str
    source_hash: str
    config_hash: str
    deadline: float
    limits: SecurityLimits
    secrets: tuple[str, ...] = field(default=(), repr=False)
    grants: tuple[WriteGrant, ...] = ()
    _seal: str = field(default="", repr=False)


def _body(ctx):
    fields = asdict(ctx)
    fields.pop("_seal")
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False).encode()


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("Expected pinned SHA-256")


def source_inventory_hash(root):
    # Versioned canonical mapping avoids ambiguous path/content concatenation.
    # Legacy fingerprint algorithms and frozen artifacts are deliberately unchanged.
    facts=inventory(no_links(Path(root)))
    raw=json.dumps({"policy":"vgar-bound-source-v1","files":facts},sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")
    return "sha256:"+hashlib.sha256(raw).hexdigest()


class ContextAuthority:
    """Construct only from trusted operator/bootstrap code, never a tool handler's JSON."""
    def __init__(self, state_root: Path):
        self.state_root = no_links(state_root).resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        key_path = self.state_root/".authority-key"
        with locked(self.state_root/".bootstrap.lock"):
            no_links(key_path)
            if not key_path.exists():
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(random_secrets.token_bytes(32)); stream.flush(); os.fsync(stream.fileno())
            self._key = key_path.read_bytes()
        if len(self._key) != 32:
            raise ValueError("Invalid authority key; operator recovery required")
        self.id = hashlib.sha256(str(self.state_root).encode()+self._key).hexdigest()
        _AUTHORITIES[self.id] = self

    def _sign(self, ctx):
        return replace(ctx, _seal=hmac.new(self._key, _body(ctx), hashlib.sha256).hexdigest())

    def grant(self, ctx: BoundContext, operation: str, input_hash: str, *, expires_at=None):
        check_context(ctx)
        if ctx.authority_id != self.id or not isinstance(operation, str) or not operation:
            raise ValueError("Authority/operation mismatch")
        _hash(input_hash)
        expiry = ctx.deadline if expires_at is None else expires_at
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not math.isfinite(expiry):
            raise ValueError("Invalid grant expiry")
        grant = WriteGrant(uuid4().hex, operation, input_hash, min(expiry, ctx.deadline))
        return self._sign(replace(ctx, grants=ctx.grants+(grant,)))


def bind_context(authority: ContextAuthority, *, repo_root, lease_root, output_root,
                 request_id, run_id, task_id, snapshot_hash, source_hash, config_hash,
                 deadline, limits=None, secrets=()):
    if type(authority) is not ContextAuthority or _AUTHORITIES.get(authority.id) is not authority:
        raise ValueError("Host authority required")
    paths = [no_links(p).resolve(strict=True) for p in (repo_root, lease_root, output_root)]
    if not all(p.is_dir() for p in paths):
        raise ValueError("Roots must be directories")
    repo, lease, output = paths
    roots=(*paths,authority.state_root)
    if any(a==b or a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError("Source/lease/output/state roots must be pairwise disjoint")
    for value in (request_id, run_id, task_id):
        if not isinstance(value, str) or not value or any(ord(c)<32 for c in value):
            raise ValueError("Invalid bound identity")
    for value in (snapshot_hash, source_hash, config_hash):
        _hash(value)
    if source_hash!=source_inventory_hash(repo):
        raise ValueError("Source inventory does not match host binding")
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline) or deadline <= time.time():
        raise ValueError("Context deadline must be finite and in the future")
    if any(not isinstance(v, str) or len(v)<4 for v in secrets):
        raise ValueError("Secret redaction values must have at least four characters")
    limits = limits or SecurityLimits()
    if type(limits) is not SecurityLimits:
        raise ValueError("Host SecurityLimits required")
    return authority._sign(BoundContext(authority.id, repo, lease, output, authority.state_root,
                          request_id, run_id, task_id, snapshot_hash, source_hash, config_hash,
                          deadline, limits, tuple(secrets)))


def _verified(ctx):
    if type(ctx) is not BoundContext:
        raise ValueError("Host-bound context required; model dictionaries are not capabilities")
    authority = _AUTHORITIES.get(ctx.authority_id)
    if authority is None or not hmac.compare_digest(ctx._seal, hmac.new(authority._key, _body(ctx), hashlib.sha256).hexdigest()):
        raise ValueError("Context authority/binding mismatch")
    for root in (ctx.repo_root, ctx.lease_root, ctx.output_root, ctx.state_root):
        no_links(root)
        if not root.is_dir():
            raise ValueError("Bound root missing")
    return authority


def _cancel_path(ctx):
    key = hashlib.sha256(json.dumps([str(ctx.repo_root),ctx.run_id,ctx.request_id,ctx.task_id,ctx.snapshot_hash],separators=(",",":")).encode()).hexdigest()
    return ctx.state_root/"cancelled"/key


@contextmanager
def request_commit_guard(ctx):
    _verified(ctx)
    path=ctx.state_root/"locks"/("request-"+_cancel_path(ctx).name+".lock")
    with locked(path,timeout=ctx.limits.lock_seconds):
        yield


def check_context(ctx):
    _verified(ctx)
    if time.time() >= ctx.deadline:
        raise ValueError("Context expired")
    if (ctx.authority_id,_cancel_path(ctx).name) in _CANCELLED or _cancel_path(ctx).exists():
        raise ValueError("Request cancelled")
    return ctx


def check_source(ctx):
    check_context(ctx)
    if source_inventory_hash(ctx.repo_root)!=ctx.source_hash:
        raise ValueError("Bound source inventory changed")
    return ctx


def cancel_request(ctx):
    _verified(ctx)
    with request_commit_guard(ctx):
        _CANCELLED.add((ctx.authority_id,_cancel_path(ctx).name))
        path = _cancel_path(ctx)
        no_links(path); path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return
        with os.fdopen(fd, "wb") as stream:
            stream.write(b"cancelled\n"); stream.flush(); os.fsync(stream.fileno())


def request_cancelled(ctx):
    _verified(ctx)
    return (ctx.authority_id,_cancel_path(ctx).name) in _CANCELLED or _cancel_path(ctx).exists()


def authorize_write(ctx, operation, input_hash):
    check_context(ctx); _hash(input_hash)
    candidates = [g for g in ctx.grants if g.operation == operation and g.input_hash == input_hash]
    if not candidates:
        raise ValueError("No host write grant for operation/input binding")
    grant = candidates[-1]
    if time.time() >= grant.expires_at:
        raise ValueError("Write grant expired")
    with locked(ctx.state_root/"locks"/("repo-"+lock_key(ctx.repo_root)+".lock"), timeout=ctx.limits.lock_seconds, deadline=ctx.deadline):
        check_context(ctx)
        if time.time() >= grant.expires_at:
            raise ValueError("Write grant expired")
        path = ctx.state_root/"used"/grant.grant_id
        no_links(path); path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError("Write grant already used") from None
        with os.fdopen(fd, "wb") as stream:
            stream.write(hashlib.sha256(_body(ctx)).hexdigest().encode()+b"\n")
            stream.flush(); os.fsync(stream.fileno())
    return grant


def current_context():
    return _CURRENT.get()


@contextmanager
def request_scope(ctx):
    check_context(ctx)
    token = _CURRENT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT.reset(token)
