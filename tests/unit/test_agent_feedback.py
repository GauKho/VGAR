"""Host-built retry feedback: read from a failed run record, never written by the agent."""
from vgar.agents.feedback import build_feedback

KEYS = {"task_id", "source_run_id", "category", "message"}


def test_parse_error_feedback_names_the_unprefixed_line():
    record = {"task_id": "single_file_login", "run_id": "r1", "status": "FAIL", "reason": "PATCH_PARSE_ERROR",
              "error_detail": {"message": "Invalid hunk body",
                               "parser_diagnostics": {"invalid_body_lines": [{"raw_line": 5, "text": "    return name"}]}}}
    feedback = build_feedback(record)
    assert set(feedback) == KEYS and all(isinstance(v, str) and v for v in feedback.values())
    assert feedback["category"] == "PATCH_PARSE_ERROR" and feedback["source_run_id"] == "r1"
    assert "Line 5" in feedback["message"] and "Invalid hunk body" in feedback["message"]


def test_parse_error_feedback_reports_count_mismatch():
    record = {"task_id": "t", "run_id": "r1", "status": "FAIL", "reason": "PATCH_PARSE_ERROR",
              "error_detail": {"message": "Bad counts", "parser_diagnostics": {
                  "hunk_header": "@@ -1,3 +1,3 @@", "expected_counts": {"old": 3, "new": 3},
                  "actual_counts": {"old": 2, "new": 3}, "invalid_body_lines": []}}}
    assert "declares old=3 new=3 but the body has old=2 new=3" in build_feedback(record)["message"]


def test_test_failure_feedback_lists_failing_tests():
    record = {"task_id": "t", "run_id": "r1", "status": "FAIL", "reason": "TEST_FAILED",
              "stages": {"verification": {"reasons": [], "tests": {"outcomes": {
                  "tests/test_a.py::t1": "FAIL", "tests/test_a.py::t2": "PASS"}}}}}
    message = build_feedback(record)["message"]
    assert "tests/test_a.py::t1" in message and "t2" not in message


def test_fallback_feedback_is_never_empty():
    record = {"task_id": "t", "run_id": "r1", "status": "ERROR", "reason": "INTERNAL_ERROR"}
    feedback = build_feedback(record)
    assert feedback["message"] and "INTERNAL_ERROR" in feedback["message"] and feedback["category"] == "INTERNAL_ERROR"
