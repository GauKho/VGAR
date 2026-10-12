"""Local SCIP input profile: isolate config discovery and make import roots explicit."""
from __future__ import annotations

import hashlib
import json
import os
import tomllib
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath


CONFIG_NAMES = ("scip-pyrightconfig.json", "pyrightconfig.json", "pyproject.toml")


def auxiliary_fingerprint(root):
    """SCIP depends on stubs and config as well as Python implementation bytes."""
    from vgar.graph.builder import IGNORED_DIRECTORY_NAMES
    root = Path(root)
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = [n for n in names if n not in IGNORED_DIRECTORY_NAMES and not (Path(directory) / n).is_symlink()]
        files.extend(Path(directory) / n for n in filenames
                     if (n.endswith(".pyi") or n in CONFIG_NAMES) and not (Path(directory) / n).is_symlink())
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def import_paths(root, requested):
    values = []
    for value in requested:
        path = PurePosixPath(value)
        if (not value or path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts
                or "\\" in value or path.as_posix() != value):
            raise ValueError("SCIP import roots must be normalized repository-relative paths")
        target = (root / value).resolve()
        if not target.is_relative_to(root):
            raise ValueError("SCIP import root escapes the repository")
        if target.is_dir() and value not in values:
            values.append(value)
    return values


@contextmanager
def local_profile(root, *, enabled=True, roots=("src", "lib")):
    """Create an exclusive, temporary config only when no JSON config exists.

    Existing JSON configs (including JSONC) are authoritative and are never rewritten.
    Root pyproject settings are copied as data. Python source and target dependencies
    are never executed or installed. An edited temporary file is retained, not deleted.
    """
    root = Path(root).resolve()
    paths = import_paths(root, roots)
    before = auxiliary_fingerprint(root)
    if not enabled:
        yield {"mode": "native", "auxiliary_inputs": before}
        return
    for name in CONFIG_NAMES[:2]:
        if (root / name).exists():
            yield {"mode": "existing_json", "config": name, "auxiliary_inputs": before,
                   "note": "Existing config preserved; import roots are not automatically overridden"}
            if auxiliary_fingerprint(root) != before:
                raise ValueError("SCIP config or stubs changed during indexing")
            return
    settings = {}
    if (root / "pyproject.toml").exists():
        settings = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("tool", {}).get("pyright", {})
    settings = dict(settings)
    extras = settings.get("extraPaths", [])
    if not isinstance(extras, list) or not all(isinstance(p, str) for p in extras):
        raise ValueError("Pyright extraPaths must be a list of paths")
    settings["extraPaths"] = list(dict.fromkeys([*extras, *paths]))
    settings.setdefault("include", ["."])
    settings.setdefault("exclude", ["**/node_modules", "**/__pycache__", "**/.*", "**/build", "**/dist"])
    target = root / CONFIG_NAMES[0]
    data = (json.dumps(settings, sort_keys=True, indent=2) + "\n").encode("utf-8")
    # Exclusive creation also prevents two workers from silently overriding each other.
    with target.open("xb") as stream:
        stream.write(data)
    try:
        yield {"mode": "managed_local", "config": target.name, "settings": settings,
               "settings_sha256": hashlib.sha256(data).hexdigest(), "auxiliary_inputs": before}
        expected = before | {target.name: hashlib.sha256(data).hexdigest()}
        if auxiliary_fingerprint(root) != expected:
            raise ValueError("SCIP config or stubs changed during indexing")
    finally:
        if target.is_file() and target.read_bytes() == data:
            target.unlink()


def runtime_fingerprint(command):
    """Include the actual bundled JS, not just npm's tiny entry-point wrapper."""
    paths = {Path(arg).resolve() for arg in command if Path(arg).is_file()}
    for path in list(paths):
        if path.name == "index.js" and (path.parent / "dist/scip-python.js").is_file():
            paths.update([path.parent / "dist/scip-python.js", path.parent / "package.json"])
        if path.name == "langserver.index.js" and (path.parent / "dist/pyright-langserver.js").is_file():
            paths.update([path.parent / "dist/pyright-langserver.js", path.parent / "package.json"])
            paths.update((path.parent / "dist").glob("*.js"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
