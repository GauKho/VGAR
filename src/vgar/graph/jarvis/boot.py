"""Entry point of the JARVIS image: keep out the files JARVIS cannot parse, run it, leave the output readable by the host."""
import ast
import importlib.metadata  # noqa: F401  # loaded before JARVIS installs its import hooks, which break this import on Python 3.11
import json
import os
import runpy
import sys
from collections.abc import Callable
from pathlib import Path

# JARVIS walks the AST recursively. Measured on this image it crashed from depth 255 (an elif ladder); real repositories stay under 30.
MAX_AST_DEPTH = 150


def _too_deep(tree: ast.AST) -> bool:
    stack = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_AST_DEPTH:
            return True
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return False


def parsable_files(source: Path) -> tuple[list[Path], list[str]]:
    """Split the Python files under source into those JARVIS can read and the relative paths of the others.

    A file JARVIS cannot parse makes it drop the file silently or crash, depending on where the file sits in the list;
    a very deep AST makes it crash with RecursionError. Either way one file must not cost the whole repository its result.
    """
    good: list[Path] = []
    skipped: list[str] = []
    for path in sorted(source.rglob("*.py"), key=lambda item: item.relative_to(source).as_posix()):
        try:
            # The same read as JARVIS's processing/base.py, under the UTF-8 locale of the container.
            with open(path, "rt", encoding="utf-8", errors="ignore") as handle:
                usable = not _too_deep(ast.parse(handle.read(), filename=str(path)))
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            usable = False
        if usable:
            good.append(path)
        else:
            skipped.append(path.relative_to(source).as_posix())
    return good, skipped


def run_jarvis_cli(files: list[Path], package: Path, out: Path) -> None:
    """Run JARVIS the way its command line does, in its default mode."""
    sys.argv = ["jarvis_cli.py", *map(str, files), "--package", str(package), "-o", str(out / "graph.json")]
    runpy.run_path(str(Path(__file__).with_name("jarvis_cli.py")), run_name="__main__")


def main(source: Path = Path("/src"), out: Path = Path("/out"),
         analyze: Callable[[list[Path], Path, Path], None] = run_jarvis_cli) -> int:
    """Analyse the files under source and write graph.json and skipped.json to out."""
    try:
        good, skipped = parsable_files(source)
        (out / "skipped.json").write_text(json.dumps(skipped), encoding="utf-8")
        if good:
            analyze(good, source, out)
        else:
            (out / "graph.json").write_text("{}", encoding="utf-8")
    finally:
        # The container runs as root; a Linux host could not delete the output otherwise.
        for path in out.rglob("*"):
            os.chmod(path, 0o777)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
