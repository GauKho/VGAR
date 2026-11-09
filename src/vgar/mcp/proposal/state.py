"""Serialized session transitions and generic atomic publication, not graph ingest."""
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from vgar.repair.evidence import atomic_json

from .context import authorize_write, check_context, check_source, request_commit_guard
from .locking import lock_key, locked, no_links
from .security import resolve_read_path


@contextmanager
def repo_guard(ctx, *, cancel_event=None):
    check_context(ctx)
    with locked(ctx.state_root/"locks"/("repo-"+lock_key(ctx.repo_root)+".lock"),timeout=ctx.limits.lock_seconds,deadline=ctx.deadline,cancel_event=cancel_event):
        check_context(ctx)
        yield


def _commit(run):
    return {name:hashlib.sha256(no_links(run/name).read_bytes()).hexdigest() for name in ("session.json","run_record.json")}


def verify_commit(run):
    commit=no_links(run/"session_commit.json")
    if no_links(run/"mcp_state_managed.json").exists() and not commit.is_file():
        raise ValueError("Session integrity: managed commit missing")
    if commit.exists() and json.loads(commit.read_text(encoding="utf-8"))!=_commit(run):
        raise ValueError("Session integrity: commit does not match durable state")


@contextmanager
def session_guard(root: Path, run: Path):
    root=no_links(root).resolve(strict=True); run=no_links(run).resolve(strict=True)
    if run==root or not run.is_relative_to(root):
        raise ValueError("Session outside leased run root")
    if not all(no_links(run/n).is_file() for n in ("session.json","run_record.json")):
        raise ValueError("Session records missing")
    with locked(root/".mcp-locks"/(lock_key(run)+".lock")):
        verify_commit(run)
        before=_commit(run)
        atomic_json(run/"mcp_state_managed.json",{"managed":True})
        try:
            yield
        except BaseException:
            if _commit(run)==before and not (run/"session_commit.json").exists():
                atomic_json(run/"session_commit.json",before)
            raise
        else:
            atomic_json(run/"session_commit.json",_commit(run))


def seal_new_session(root, run):
    with session_guard(root, Path(run)):
        pass


def manifest_input_hash(relative,value,expected_revision=None):
    raw=json.dumps({"path":relative,"value":value,"expected_revision":expected_revision},sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def publish_manifest(ctx, relative, value, *, input_hash, expected_revision=None):
    if input_hash!=manifest_input_hash(relative,value,expected_revision):
        raise ValueError("Publication payload/input hash mismatch")
    with repo_guard(ctx):
        authorize_write(ctx,"publish",input_hash)
        destination=resolve_read_path(ctx.output_root,relative,protect=True)
        revision=hashlib.sha256(destination.read_bytes()).hexdigest() if destination.is_file() else None
        if revision!=expected_revision:
            raise ValueError("Stale publication revision")
        check_source(ctx)
        with tempfile.NamedTemporaryFile(dir=ctx.output_root,prefix=".publication-",suffix=".json",delete=False) as file:
            stage=Path(file.name)
        try:
            atomic_json(stage,{"binding":{"run_id":ctx.run_id,"task_id":ctx.task_id,"snapshot_hash":ctx.snapshot_hash,"source_hash":ctx.source_hash,"config_hash":ctx.config_hash},"value":value})
            check_source(ctx)
            no_links(destination)
            destination.parent.mkdir(parents=True,exist_ok=True)
            no_links(destination)
            with request_commit_guard(ctx):
                check_context(ctx)
                os.replace(stage,destination)
        finally:
            stage.unlink(missing_ok=True)
    return destination
