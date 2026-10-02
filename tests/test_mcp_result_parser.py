from __future__ import annotations

from dataclasses import dataclass

import pytest

from vgar.mcp.result_parser import parse_mcp_json_result


def test_parse_dict_passthrough() -> None:
    payload = {"status": "OK", "symbols": []}
    assert parse_mcp_json_result(payload) == payload


def test_parse_raw_json_string() -> None:
    assert parse_mcp_json_result('{"status":"OK"}') == {"status": "OK"}


def test_parse_langchain_content_block_list() -> None:
    result = [{"type": "text", "text": '{"status":"OK","symbols":[]}'}]
    assert parse_mcp_json_result(result) == {"status": "OK", "symbols": []}


@dataclass
class _TextBlock:
    text: str


def test_parse_textcontent_like_object() -> None:
    assert parse_mcp_json_result([_TextBlock('{"status":"OK"}')]) == {
        "status": "OK"
    }


def test_reject_unsupported_result() -> None:
    with pytest.raises(TypeError):
        parse_mcp_json_result([{"type": "image"}])
