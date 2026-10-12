"""Read the navigation subset of SCIP protobuf, skipping unknown fields.

Field numbers follow https://github.com/scip-code/scip/blob/main/scip.proto.
No generated bindings or runtime compiler are required. Unsupported encodings
fail explicitly so the caller can select the static fallback.
"""
from __future__ import annotations

from typing import Iterator


def _varint(data: memoryview, position: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if position >= len(data):
            raise ValueError("Truncated SCIP varint")
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
    raise ValueError("Invalid SCIP varint")


def _fields(data: bytes | memoryview) -> Iterator[tuple[int, int | memoryview]]:
    view, position = memoryview(data), 0
    while position < len(view):
        tag, position = _varint(view, position)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid SCIP field number")
        if wire == 0:
            value, position = _varint(view, position)
            yield number, value
        elif wire in (1, 2, 5):
            size = 8 if wire == 1 else 4
            if wire == 2:
                size, position = _varint(view, position)
            if size > len(view) - position:
                raise ValueError("Truncated SCIP field")
            if wire == 2:
                yield number, view[position:position + size]
            position += size
        else:
            raise ValueError(f"Unsupported SCIP wire type {wire}")


def _packed(data: memoryview) -> list[int]:
    result, position = [], 0
    while position < len(data):
        value, position = _varint(data, position)
        result.append(value)
    return result


def _text(value: memoryview) -> str:
    return value.tobytes().decode("utf-8")


def _occurrence(data: memoryview) -> dict:
    result = {"symbol": "", "roles": 0, "range": []}
    legacy, typed = [], None
    for number, value in _fields(data):
        if number == 1:
            legacy.extend([value] if isinstance(value, int) else _packed(value))
        elif number == 2:
            result["symbol"] = _text(value)
        elif number == 3:
            result["roles"] = value
        elif number in (8, 9):
            bounds = dict(_fields(value))
            typed = [bounds.get(i, 0) for i in range(1, 4 if number == 8 else 5)]
    bounds = typed if typed is not None else legacy
    if len(bounds) == 3:
        bounds = [bounds[0], bounds[1], bounds[0], bounds[2]]
    if len(bounds) != 4 or any(not isinstance(x, int) or x < 0 for x in bounds):
        raise ValueError("Invalid SCIP occurrence range")
    if tuple(bounds[:2]) > tuple(bounds[2:]):
        raise ValueError("Reversed SCIP occurrence range")
    result["range"] = bounds
    return result


def read_index(data: bytes) -> dict:
    result = {"root_uri": "", "tool": "", "tool_version": "", "text_encoding": 0, "documents": []}
    for number, value in _fields(data):
        if number == 1:
            for key, field in _fields(value):
                if key == 2:
                    tool = dict(_fields(field))
                    result["tool"] = _text(tool.get(1, memoryview(b"")))
                    result["tool_version"] = _text(tool.get(2, memoryview(b"")))
                elif key == 3:
                    result["root_uri"] = _text(field)
                elif key == 4:
                    result["text_encoding"] = field
        elif number == 2:
            doc = {"path": "", "encoding": 0, "occurrences": []}
            for key, field in _fields(value):
                if key == 1:
                    doc["path"] = _text(field)
                elif key == 2:
                    doc["occurrences"].append(_occurrence(field))
                elif key == 6:
                    doc["encoding"] = field
            result["documents"].append(doc)
    if not result["root_uri"] or not result["documents"]:
        raise ValueError("SCIP index has no project root or documents")
    if result["text_encoding"] not in (0, 1):
        raise ValueError("Only UTF-8 source files are supported")
    return result
