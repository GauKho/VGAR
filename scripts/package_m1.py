"""Package the current source checkout without local runtimes or run outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = {"src", "scripts", "tests", "configs", "docs"}
ROOT_FILES = {"README.md", "pyproject.toml", ".gitignore", ".env.example"}
FIXTURES = {"artifacts/fixture_graph.json", "artifacts/sample_graph.json", "artifacts/sample_graph.db"}
EVIDENCE_DIRS = {"context-retrieval", "graph-quality", "task-grounding", "tokenizer-acceptance"}
REQUIRED = {
    "README.md", "pyproject.toml", "scripts/requirements_m1.txt",
    "scripts/smoke_w7_w8_m1.py", "src/vgar/graph/retrieval.py",
    "src/vgar/contracts/context.py", "src/vgar/contracts/handoff.py",
    "configs/scip/package-lock.json", "configs/lsp/package-lock.json",
    *FIXTURES,
}


def git(*args: str, input_data: bytes | None = None, allowed_codes=(0,)) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode not in allowed_codes:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def package_paths() -> list[str]:
    candidates = set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
                     .decode("utf-8").strip("\0").split("\0")) - {""}
    ignored = set(git("check-ignore", "--no-index", "-z", "--stdin",
                      input_data=("\0".join(sorted(candidates)) + "\0").encode("utf-8"),
                      allowed_codes=(0, 1)).decode("utf-8").strip("\0").split("\0"))
    selected = []
    for name in sorted(candidates - ignored):
        parts = PurePosixPath(name).parts
        if (name not in ROOT_FILES and name not in FIXTURES and parts[0] not in SOURCE_DIRS
                and not (len(parts) > 3 and parts[:2] == ("artifacts", "m1")
                         and parts[2] in EVIDENCE_DIRS)):
            continue
        path = ROOT / name
        if not path.exists():
            continue
        # Refuse links rather than bringing unrelated files into a handoff.
        if any(parent.is_symlink() or (getattr(parent.lstat(), "st_file_attributes", 0)
                                       & stat.FILE_ATTRIBUTE_REPARSE_POINT)
               for parent in (path, *path.parents) if parent != ROOT and ROOT in parent.parents):
            raise ValueError(f"Cannot package a filesystem link: {name}")
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Package path escapes checkout: {name}")
        if path.is_file():
            selected.append(name)
    missing = REQUIRED - set(selected)
    if missing:
        raise ValueError(f"Required package files missing: {', '.join(sorted(missing))}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Print the source file list without creating a ZIP")
    parser.add_argument("--output", type=Path, help="New ZIP path; defaults to dist/vgar-m1-<UTC timestamp>.zip")
    args = parser.parse_args()
    paths = package_paths()
    if args.list:
        print("\n".join(paths))
        return 0
    now = datetime.now(timezone.utc)
    output = (args.output or ROOT / "dist" / f"vgar-m1-{now:%Y%m%dT%H%M%S%fZ}.zip").resolve()
    if output.suffix.lower() != ".zip":
        parser.error("output must be a .zip file")
    if output.exists():
        parser.error("output already exists; choose a new path")
    if output in {ROOT / path for path in paths}:
        parser.error("output cannot overwrite a source file")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format": "vgar.source-package.v1", "created_utc": now.isoformat(),
        "base_commit": git("rev-parse", "HEAD").decode().strip(),
        "includes_working_tree_changes": True,
        "default_resolver": "static", "optional_resolvers": ["scip", "lsp", "scip-lsp"],
        "scope": "Source and fixtures; model/tokenizer assets, Node runtimes and recent run evidence excluded",
        "files": {},
    }
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name in paths:
            data = (ROOT / name).read_bytes()
            archive.writestr(f"VGAR-M1/{name}", data)
            manifest["files"][name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        archive.writestr("VGAR-M1/package_manifest.json", json.dumps(manifest, indent=2) + "\n")
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
    print(json.dumps({"archive": str(output), "files": len(paths), "bytes": output.stat().st_size,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
