"""AST function extraction, no repository code execution and no graph dependency."""
import ast
import io
import tokenize
from collections import Counter
from pathlib import PurePosixPath

from .evidence import sha256


def normalize_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"Expected relative POSIX path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        raise ValueError(f"Unsafe path: {value!r}")
    return path.as_posix()


def is_source(path):
    parts = PurePosixPath(path).parts
    return path.endswith(".py") and not any(p.lower() in {"tests", "test", "testing", "docs", "doc", ".venv", "venv", "__pycache__"} for p in parts) and not PurePosixPath(path).name.startswith("test_") and not PurePosixPath(path).stem.endswith("_test")


def decode_source(data):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


def module_name(path):
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts.pop(0)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__init__"


def physical_lines(text, keepends=False):
    """Match Python/unified diff CR/LF coordinates, not Unicode splitlines separators."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.split("\n")
    if parts[-1] == "":
        parts.pop()
    if keepends:
        return [line + ("\n" if i < len(parts) - 1 or normalized.endswith("\n") else "") for i, line in enumerate(parts)]
    return parts


def entities(path, source):
    tree = ast.parse(source, filename=path)
    output = []
    module = module_name(path)

    def visit(node, parents=(), parent_kind=None):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol = ".".join((module, *parents, node.name))
            start = min([node.lineno, *[d.lineno for d in node.decorator_list]])
            output.append({"parent_id": f"{path}::{symbol}", "path": path, "symbol": symbol,
                           "kind": "method" if parent_kind == "class" else "function", "start_line": start,
                           "start_col": 0 if node.decorator_list else node.col_offset,
                           "end_line": node.end_lineno, "end_col": node.end_col_offset,
                           "definition_line": node.lineno, "depth": len(parents)})
            parents = (*parents, node.name)
            parent_kind = "function"
        elif isinstance(node, ast.ClassDef):
            parents = (*parents, node.name)
            parent_kind = "class"
        for child in ast.iter_child_nodes(node):
            visit(child, parents, parent_kind)

    visit(tree)
    counts = Counter(d["parent_id"] for d in output)
    for definition in output:
        if counts[definition["parent_id"]] > 1:
            definition["parent_id"] += f"@definition:{definition['start_line']}:{definition['end_line']}"
    return output


def extract_chunks(sources, window_lines=80, overlap_lines=16):
    if window_lines < 1 or overlap_lines < 0 or overlap_lines >= window_lines:
        raise ValueError("Invalid window/overlap")
    chunks, failures = [], []
    for raw_path, source in sorted(sources.items()):
        path = normalize_path(raw_path)
        if not is_source(path):
            continue
        try:
            defs = entities(path, source)
        except (SyntaxError, ValueError) as exc:
            failures.append({"path": path, "error": type(exc).__name__, "message": str(exc)})
            continue
        lines = physical_lines(source, keepends=True)
        covered = set()
        spans = list(defs)
        for item in defs:
            covered.update(range(item["start_line"], item["end_line"] + 1))
        # Non-function code is stored in contiguous source ranges, not fabricated joined lines.
        start = None
        for number in range(1, len(lines) + 2):
            included = number <= len(lines) and number not in covered and bool(lines[number - 1].strip())
            if included and start is None:
                start = number
            if start is not None and not included:
                spans.append({"parent_id": f"{path}::{module_name(path)}::<module>", "path": path,
                              "symbol": f"{module_name(path)}::<module>", "kind": "module", "start_line": start,
                              "end_line": number - 1, "start_col": 0, "end_col": len(lines[number - 2].rstrip("\r\n").encode("utf-8")), "depth": 0})
                start = None
        for entity in spans:
            begin = entity["start_line"]
            while begin <= entity["end_line"]:
                end = min(begin + window_lines - 1, entity["end_line"])
                snippet = "".join(lines[begin - 1:end])
                chunk = dict(entity, chunk_id=f"{entity['parent_id']}@{begin}:{end}", parent_start_line=entity["start_line"],
                             parent_end_line=entity["end_line"], start_line=begin, end_line=end, snippet=snippet,
                             content_hash=sha256(snippet), source_hash=sha256(source))
                chunk["text"] = f"{path} {entity['symbol']}\n{snippet}"
                chunks.append(chunk)
                if end == entity["end_line"]:
                    break
                begin += window_lines - overlap_lines
    return chunks, failures
