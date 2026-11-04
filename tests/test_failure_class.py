"""Spec 2026-11-03-m3-w12-trace §4 E3: one outcome class per run, shared by the agent host and the batch runner."""
import pytest

from vgar.evaluation.failure_class import CLASSES, classify


@pytest.mark.parametrize("status,code,detail,applied,expected", [
    ("PASS", None, None, True, "VERIFIED"),
    ("ERROR", "INTERNAL_ERROR", "Docker operation incomplete: ['info', '--format']", False, "INFRA"),
    ("ERROR", "INTERNAL_ERROR", "No such image: swebench/x", False, "INFRA"),
    ("ERROR", "RUNNER_INFRA_ERROR", None, False, "INFRA"),
    ("ERROR", "MCP_TRANSPORT_ERROR", None, False, "INFRA"),
    ("ERROR", "INTERNAL_ERROR", "Tokenizer worker failed: Full prompt exceeds model input budget", False, "PROTOCOL"),
    ("ERROR", "ADMISSION_REJECTED", None, False, "PROTOCOL"),
    ("ERROR", "TASK_EXCLUDED", None, False, "PROTOCOL"),
    ("ERROR", "TASK_INPUT_MISSING", None, False, "PROTOCOL"),
    ("ERROR", "SELECTOR_OUTSIDE_SCOPE", None, False, "PROTOCOL"),
    ("ERROR", "GENERATION_TIMEOUT", None, False, "MODEL"),
    ("ERROR", "GENERATION_ERROR", None, False, "MODEL"),
    ("FAIL", "PATCH_PARSE_ERROR", None, False, "MODEL"),
    ("FAIL", "NO_OP", None, False, "MODEL"),
    ("FAIL", "CONTEXT_NOT_FOUND", None, False, "MODEL"),
    ("FAIL", "TEST_FAILED", None, True, "MODEL"),
    ("FAIL", "STATIC_REGRESSION", None, True, "MODEL"),
    ("FAIL", "SOMETHING_NEW", None, True, "MODEL"),
    ("ERROR", "SOMETHING_NEW", None, False, "UNCLASSIFIED"),
    ("ERROR", "VERIFICATION_INCOMPLETE", None, False, "UNCLASSIFIED"),
])
def test_classify(status, code, detail, applied, expected):
    assert classify(status, code, detail, applied=applied) == expected
    assert expected in CLASSES
