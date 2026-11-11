"""Bounded reads and log sanitization; repository text never grants authority."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PureWindowsPath

from vgar.observability.redact import redact_text
from vgar.repair.workspace import safe_relative_path

from .context import check_context, current_context
from .locking import is_reparse, locked, no_links

_SECRET = re.compile(r"(?i)(password|secret|authorization|credential|api[_-]?key|access[_-]?token|^token$|^grants?$|^grant_id$|^_?seal$|^authority(_id)?$)")
_PRIVATE = {"diff", "patch", "prompt", "messages", "issue_text", "raw_text"}
_DEVICES = {"CON", "PRN", "AUX", "NUL", *("COM"+str(n) for n in range(1,10)), *("LPT"+str(n) for n in range(1,10))}


def resolve_read_path(root: Path, relative: str, *, protect=True):
    root = Path(root).absolute()
    no_links(root)
    if is_reparse(root) or not root.is_dir():
        raise ValueError("Read root is missing or linked")
    if not isinstance(relative, str) or "\0" in relative:
        raise ValueError("Invalid relative path")
    part = safe_relative_path(relative)
    if PureWindowsPath(relative).drive:
        raise ValueError("Model path cannot select a drive")
    for name in part.parts:
        if ":" in name or name.endswith(("."," ")) or name.split(".")[0].upper() in _DEVICES or any(ord(c)<32 for c in name):
            raise ValueError("Unsafe Windows path alias")
        low = name.casefold()
        if protect and (low in {".git", ".codex", ".agents", ".aws", ".ssh", "id_rsa", "id_ed25519"} or low.startswith(".env") or low.endswith((".pem", ".key", ".p12", ".pfx"))):
            raise ValueError("Protected secret/control path")
    path = root/part
    no_links(path)
    target = path.resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Path leaves leased root")
    return target


def read_bound_file(ctx, relative):
    check_context(ctx)
    return read_lease_bytes(ctx.lease_root,relative,ctx.limits.read_bytes)[0]


def read_lease_bytes(root,relative,cap):
    """Validate the opened handle before reading, including reparse/parent swaps."""
    root=Path(root).absolute()
    path=resolve_read_path(root,relative)
    if os.name=="nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
        kernel.CreateFileW.restype=w.HANDLE
        handle=kernel.CreateFileW(str(path),0x80000000,7,None,3,0x200080,None)
        if handle==ctypes.c_void_p(-1).value:
            raise OSError(ctypes.get_last_error(),"Cannot open leased file")
        try:
            kernel.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD]
            buffer=ctypes.create_unicode_buffer(32768)
            length=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0)
            if not length or length>=len(buffer):
                raise ValueError("Cannot validate opened file path")
            final=buffer.value.removeprefix("\\\\?\\")
            if not Path(final).is_relative_to(root):
                raise ValueError("Opened file leaves leased root")
            fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
            handle=None
        finally:
            if handle is not None:
                kernel.CloseHandle.argtypes=[w.HANDLE]; kernel.CloseHandle(handle)
    else:
        descriptors=[]
        try:
            current=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW); descriptors.append(current)
            parts=path.relative_to(root).parts
            for part in parts[:-1]:
                current=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current); descriptors.append(current)
            fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=current)
        finally:
            for opened in reversed(descriptors): os.close(opened)
    with os.fdopen(fd,"rb") as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or getattr(info,"st_file_attributes",0)&0x400:
            raise ValueError("Opened path is not a regular unlinked file")
        return stream.read(cap),info.st_size


def scrub_secrets(value,secrets):
    if isinstance(value,str):
        for secret in secrets:value=value.replace(secret,"[REDACTED]")
        return redact_text(value)
    if isinstance(value,dict):return {k:scrub_secrets(v,secrets) for k,v in value.items()}
    if isinstance(value,list):return [scrub_secrets(v,secrets) for v in value]
    return value


def sanitize(value, *, secret_values=(), depth=0):
    if depth>12:
        return "[DEPTH_LIMIT]"
    ctx = current_context()
    secrets = tuple(secret_values)+(ctx.secrets if ctx else ())
    if isinstance(value, str):
        text = redact_text(value)
        for secret in secrets:
            text = text.replace(secret,"[REDACTED]")
        return text
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if _SECRET.search(str(key)):
                result[key] = "[REDACTED]"
            elif str(key).lower() in _PRIVATE:
                raw = json.dumps(item,ensure_ascii=False,default=str).encode()
                result[key] = {"sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)}
            else:
                result[key] = sanitize(item,secret_values=secrets,depth=depth+1)
        return result
    if isinstance(value, (list,tuple)):
        return [sanitize(x,secret_values=secrets,depth=depth+1) for x in value]
    return value


def read_audit(ctx, cursor=0, *, output_bytes=None):
    check_context(ctx)
    if type(cursor) is not int or cursor<0:
        raise ValueError("Invalid audit cursor")
    if output_bytes is not None and (type(output_bytes) is not int or not 1 <= output_bytes <= min(262144, ctx.limits.audit_bytes)):
        raise ValueError("Invalid serialized audit page limit")
    path = no_links(ctx.output_root/"audit.jsonl")
    with locked(path.with_name(path.name+".lock"),timeout=ctx.limits.lock_seconds,deadline=ctx.deadline):
        check_context(ctx)
        if not path.is_file():
            raise ValueError("Bound audit log missing")
        with path.open("rb") as stream:
            size = stream.seek(0,2)
            if cursor>size:
                raise ValueError("Audit cursor outside file")
            if size:
                stream.seek(-1,2)
                if stream.read(1)!=b"\n":
                    raise ValueError("Audit integrity: incomplete tail")
            if cursor:
                stream.seek(cursor-1)
                if stream.read(1)!=b"\n":
                    raise ValueError("Audit cursor is not a record boundary")
            stream.seek(cursor)
            items=[]; used=0
            record_cap = min(200, ctx.limits.audit_records) if output_bytes is not None else ctx.limits.audit_records
            while len(items)<record_cap and stream.tell()<size:
                line=stream.readline(min(65537,ctx.limits.audit_bytes-used+1))
                if used+len(line)>ctx.limits.audit_bytes:
                    if not items:
                        raise ValueError("Audit record exceeds configured page capacity")
                    break
                if not line.endswith(b"\n") or len(line)>65536:
                    raise ValueError("Audit integrity: oversized record")
                item=json.loads(line)
                payload=item.get("payload",{})
                if payload.get("run_id")!=ctx.run_id or payload.get("task_id")!=ctx.task_id:
                    raise ValueError("Cross-run/task audit access refused")
                if output_bytes is not None and payload.get("snapshot_hash") != ctx.snapshot_hash:
                    raise ValueError("Cross-snapshot audit access refused")
                clean = sanitize(item, secret_values=ctx.secrets)
                if output_bytes is not None:
                    candidate = {"items": [*items, clean], "cursor": stream.tell(), "truncated": stream.tell() < size}
                    if len(json.dumps(candidate, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")) > output_bytes:
                        if not items:
                            raise ValueError("Audit record exceeds serialized page capacity")
                        break
                items.append(clean); used+=len(line); cursor=stream.tell()
    if output_bytes is not None and len(json.dumps({"items":items,"cursor":cursor,"truncated":cursor<size},ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")) > output_bytes:
        raise ValueError("Audit page header exceeds serialized byte limit")
    return {"items":items,"cursor":cursor,"truncated":cursor<size}
