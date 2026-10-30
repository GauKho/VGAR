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


def _impact(status="COMPLETE", count=7):
    items = [{"node_id": f"id:{i}", "qualified_name": f"pkg.mod.caller_{i}", "path": "pkg/mod.py",
              "kind": "Function", "hops": 1 + i % 2, "relation": "CALLS", "via": "id:changed"} for i in range(count - 1)]
    items.append({"node_id": "id:test", "qualified_name": "tests.test_mod.test_it", "path": "tests/test_mod.py",
                  "kind": "Test", "hops": 2, "relation": "TESTS", "via": "id:changed"})
    return {"repo_key": "demo", "repository_revision": "r1", "graph_version": "g1",
            "graph_hash": "sha256:" + "a" * 64, "source_hash": "sha256:" + "b" * 64, "patch_hash": "sha256:" + "c" * 64,
            "changed": [{"node_id": "id:changed", "path": "pkg/mod.py", "kind": "Function",
                         "source_range": {"start_line": 10, "start_col": 0, "end_line": 12, "end_col": 0},
                         "basis": "baseline_changed_lines",
                         "spans": [{"hunk_index": 1, "old_start": 11, "old_count": 1, "new_start": 11, "new_count": 1}]}],
            "unmapped": [],
            "impacted": {"status": status, "items": items, "max_hops": 2, "max_nodes": 200, "min_confidence": 0.6,
                         "traversed": ["CALLS", "IMPORTS", "INHERITS", "TESTS"], "unsupported": []}}


TEST_FAILED = {"task_id": "t", "run_id": "r1", "status": "FAIL", "reason": "TEST_FAILED",
               "stages": {"verification": {"reasons": [], "tests": {"outcomes": {"tests/test_a.py::t1": "FAIL"}}}}}


def test_impact_is_appended_after_the_failure_and_bounded():
    plain = build_feedback(TEST_FAILED)["message"]
    feedback = build_feedback(TEST_FAILED, impact=_impact())
    message = feedback["message"]
    assert set(feedback) == KEYS and message.startswith(plain + "\n")
    section = message[len(plain) + 1:]
    assert "pkg/mod.py:10-12" in section and "7 dependent node(s), 1 test(s)" in section
    assert section.index("tests.test_mod.test_it") < section.index("pkg.mod.caller_1")  # tests first within a hop
    assert "+2 more" in section and len(section) <= 400


def test_impact_accepts_a_report_and_marks_partial_walks():
    from vgar.contracts.impact import ImpactReport
    report = ImpactReport.model_validate(_impact(status="PARTIAL", count=2))
    message = build_feedback(TEST_FAILED, impact=report)["message"]
    assert "(partial)" in message and "more" not in message


def test_not_computed_impact_adds_nothing():
    impact = _impact()
    impact["impacted"] = {"status": "NOT_COMPUTED"}
    assert build_feedback(TEST_FAILED, impact=impact) == build_feedback(TEST_FAILED)
