"""One pruned repository inventory shared by indexing, snapshots and workspaces."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


IGNORED_DIRECTORY_NAMES = frozenset({
    ".git", ".hg", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    ".venv", ".venv-win", "venv", "__pycache__", "build", "dist", "node_modules", ".vgar",
})
VGAR_OPERATIONAL_PATHS = (
    "data/downloads", "data/gold", "data/graphs", "data/repositories",
    "results", "artifacts", "logs", "generated",
)


@dataclass(frozen=True)
class SourceScope:
    excluded_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.excluded_paths, tuple):
            raise ValueError("excluded_paths must be a tuple of repository-relative paths")
        for value in self.excluded_paths:
            if not isinstance(value, str):
                raise ValueError("excluded path must be a string")
            path = PurePosixPath(value)
            if (not value or path.is_absolute() or PureWindowsPath(value).drive or "\\" in value
                    or any(part in {"", ".", ".."} for part in value.split("/"))):
                raise ValueError(f"Invalid source-scope path: {value!r}")
        object.__setattr__(self, "excluded_paths", tuple(sorted(set(self.excluded_paths))))

    @classmethod
    def for_repository(cls, root: Path) -> "SourceScope":
        """Only this project's identity enables its operational exclusions.

        Generic repositories may contain genuine Python packages named data/results/logs.
        The profile survives a disposable copy because pyproject and src are preserved.
        """
        project = Path(root) / "pyproject.toml"
        if project.is_file() and project.stat().st_size <= 1024 * 1024 and (Path(root) / "src/vgar").is_dir():
            try:
                with project.open("rb") as stream:
                    name = tomllib.load(stream).get("project", {}).get("name")
            except (OSError, ValueError):
                name = None
            if name == "vgar-mcp":
                return cls(excluded_paths=VGAR_OPERATIONAL_PATHS)
        return cls()

    def metadata(self) -> dict:
        return {"excluded_paths": list(self.excluded_paths)}

    def excludes(self, relative: str) -> bool:
        parts = PurePosixPath(relative).parts
        return (any(part in IGNORED_DIRECTORY_NAMES or part.startswith(".m2-pytest-") for part in parts)
                or any(relative == path or relative.startswith(path + "/") for path in self.excluded_paths))

    def files(self, root: Path) -> list[tuple[str, Path]]:
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"Not a repository directory: {root}")
        found = []

        def visit(directory: Path) -> None:
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
            for entry in children:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                # Prune before stat/descent, not a filter after rglob allocated all paths.
                if self.excludes(relative):
                    continue
                stat = entry.stat(follow_symlinks=False)
                is_reparse = bool(getattr(stat, "st_file_attributes", 0) & 0x400)
                if entry.is_symlink() or is_reparse or (hasattr(path, "is_junction") and path.is_junction()):
                    raise ValueError(f"Source contains a link: {path}")
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    found.append((relative, path))
                else:
                    raise ValueError(f"Unsupported source entry: {path}")

        visit(root)
        return sorted(found)

    def python_files(self, root: Path) -> list[Path]:
        return [path for relative, path in self.files(root) if relative.endswith(".py")]
