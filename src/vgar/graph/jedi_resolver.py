from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    import jedi
except ImportError:  # pragma: no cover - exercised only in minimal deployments
    jedi = None


@dataclass(frozen=True)
class JediResolution:
    full_name: str | None
    module_path: Path | None
    line: int | None
    name: str
    symbol_type: str


class JediSymbolResolver:
    """Resolve call targets without making Jedi a hard runtime requirement."""

    def __init__(
        self,
        repository_root: Path,
        *,
        source_roots: tuple[str, ...],
        enabled: bool = True,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.enabled = enabled and jedi is not None
        self._scripts: dict[Path, object] = {}
        self._project = None
        if self.enabled:
            jedi.settings.cache_directory = str(
                Path(tempfile.gettempdir()) / "vgar-jedi-cache"
            )
            added_sys_path = [
                str(path)
                for root_name in source_roots
                if (path := self.repository_root / root_name).is_dir()
            ]
            self._project = jedi.Project(
                path=str(self.repository_root),
                added_sys_path=added_sys_path,
            )

    def resolve(
        self,
        relative_path: str,
        *,
        line: int,
        column: int,
    ) -> list[JediResolution]:
        if not self.enabled:
            return []

        file_path = (self.repository_root / relative_path).resolve()
        try:
            file_path.relative_to(self.repository_root)
        except ValueError:
            return []
        if not file_path.is_file():
            return []

        script = self._scripts.get(file_path)
        if script is None:
            script = jedi.Script(path=str(file_path), project=self._project)
            self._scripts[file_path] = script

        try:
            definitions = script.goto(
                line=line,
                column=column,
                follow_imports=True,
                follow_builtin_imports=False,
            )
            if not definitions:
                definitions = script.infer(line=line, column=column)
        except (ValueError, OSError):
            return []

        results: list[JediResolution] = []
        for definition in definitions:
            module_path = getattr(definition, "module_path", None)
            results.append(
                JediResolution(
                    full_name=getattr(definition, "full_name", None),
                    module_path=(
                        Path(module_path).resolve() if module_path is not None else None
                    ),
                    line=getattr(definition, "line", None),
                    name=definition.name,
                    symbol_type=definition.type,
                )
            )
        return results
