"""One outcome class per run (spec 2026-11-03-m3-w12-trace §4 E3), shared by the agent host and the batch runner.

Only INFRA outcomes may be rerun (D22). Unknown codes are UNCLASSIFIED rather than guessed.
"""
from __future__ import annotations

CLASSES = ("VERIFIED", "INFRA", "PROTOCOL", "MODEL", "UNCLASSIFIED")

INFRA_CODES = frozenset({"RUNNER_INFRA_ERROR", "MCP_TRANSPORT_ERROR", "TOOL_TIMEOUT"})
INFRA_DETAILS = ("Docker operation incomplete", "No such image")
PROTOCOL_CODES = frozenset({"ADMISSION_REJECTED", "TASK_EXCLUDED", "TASK_INPUT_MISSING", "SELECTOR_OUTSIDE_SCOPE",
                            "OVER_CAP"})
OVER_CAP_DETAILS = ("exceeds model input budget", "exceeds input budget")
MODEL_CODES = frozenset({"GENERATION_TIMEOUT", "GENERATION_ERROR", "PATCH_PARSE_ERROR", "NO_OP",
                         "CONTEXT_NOT_FOUND", "TEST_FAILED", "OUTPUT_TRUNCATED"})


def _timed_out(node, path: str):
    if isinstance(node, dict):
        if node.get("timed_out") is True:
            return path, node.get("timeout_seconds")
        for key, value in node.items():
            found = _timed_out(value, f"{path}.{key}" if path else str(key))
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _timed_out(value, path)
            if found:
                return found
    return None


def refine_code(code: str | None, record: dict | None) -> tuple[str | None, str | None]:
    """VERIFICATION_INCOMPLETE hides two causes (X2b 03/11): output cut at output_cap (model) or a command killed
    at its timeout (infrastructure). Returns the refined code and the run_record evidence for it."""
    stages = (record or {}).get("stages") or {}
    if code != "VERIFICATION_INCOMPLETE" or not stages:
        return code, None
    generation = stages.get("generation") or {}
    if generation.get("truncated"):
        return "OUTPUT_TRUNCATED", f"generation: output cut at {generation.get('output_tokens')} tokens"
    found = _timed_out(stages, "")
    if found:
        path, seconds = found
        after = f" after {seconds:.0f} s" if isinstance(seconds, (int, float)) else ""
        return "TOOL_TIMEOUT", f"{path.removesuffix('.command')} timed out{after}"
    return code, None


def classify(status: str | None, code: str | None, detail: str | None = None, *, applied: bool = False) -> str:
    detail = detail or ""
    if status == "PASS":
        return "VERIFIED"
    if code in PROTOCOL_CODES or any(text in detail for text in OVER_CAP_DETAILS):
        return "PROTOCOL"
    if code in INFRA_CODES or code == "INTERNAL_ERROR" or any(text in detail for text in INFRA_DETAILS):
        return "INFRA"
    if code in MODEL_CODES or (code or "").startswith("STATIC_"):
        return "MODEL"
    if applied and code != "VERIFICATION_INCOMPLETE":  # REJECT after an applied patch: the patch was judged
        return "MODEL"
    return "UNCLASSIFIED"
