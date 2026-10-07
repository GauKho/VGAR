from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from vgar.config.settings import Settings
from vgar.contracts.evidence import TestRunResult as RunResult
from vgar.mcp.audit import AuditLogger
from vgar.mcp.schemas import ToolResponse
from vgar.mcp.servers import execution_server, repository_server


@pytest.fixture
def leased(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    original = tmp_path / "original"
    for path in (root, original):
        (path / "tests").mkdir(parents=True)
        (path / "app.py").write_bytes(b"value = 0\r\n")
        (path / "tests/test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    settings = replace(Settings(), workspace_root=root, audit_log=tmp_path / "audit.jsonl")
    for server in (repository_server, execution_server):
        monkeypatch.setattr(server, "_settings", settings)
        monkeypatch.setattr(server, "_audit_logger", AuditLogger(settings.audit_log))
    return root, original, settings


def valid(response):
    ToolResponse.model_validate(response)
    assert set(response) == {"status", "data", "error", "metadata"}
    assert response["metadata"]["request_id"]
    return response


def test_host_workspace_setting_is_forwarded_and_unbound_clears_inherited_permission(leased, monkeypatch):
    from vgar.mcp.client import create_mcp_client
    root, _, settings = leased
    monkeypatch.setenv("VGAR_WORKSPACE_ROOT", "C:/unapproved")
    bound = create_mcp_client(settings)
    assert all(connection["env"]["VGAR_WORKSPACE_ROOT"] == str(root) for connection in bound.connections.values())
    unbound = create_mcp_client(Settings())
    assert all(connection["env"]["VGAR_WORKSPACE_ROOT"] == "" for connection in unbound.connections.values())


def test_original_root_is_rejected_before_write_or_execution(leased, monkeypatch):
    root, original, _ = leased
    monkeypatch.setattr(execution_server, "run_tests", lambda *args: pytest.fail("unauthorized execution"))
    before = (original / "app.py").read_bytes()
    for response in (
        repository_server.read_file(str(original), "app.py"),
        repository_server.apply_patch(str(original), "app.py", "0", "1"),
        execution_server.run_pytest(str(original), "tests", 10),
    ):
        assert valid(response)["status"] == "ERROR"
        assert response["error"]["code"] == "WORKSPACE_ACCESS_DENIED"
    assert (original / "app.py").read_bytes() == before == (root / "app.py").read_bytes()


def test_unbound_health_is_available_but_file_and_execution_tools_denied(leased, monkeypatch):
    root, _, settings = leased
    for server in (repository_server, execution_server):
        monkeypatch.setattr(server, "_settings", replace(settings, workspace_root=None))
        assert valid(server.health())["status"] == "PASS"
    for response in (repository_server.read_file(str(root), "app.py"),
                     repository_server.apply_patch(str(root), "app.py", "0", "1"),
                     execution_server.run_pytest(str(root), "tests", 10)):
        assert valid(response)["error"]["code"] == "WORKSPACE_NOT_BOUND"


def test_stale_lease_fails_closed(leased):
    root, _, _ = leased
    root.rename(root.with_name("expired"))
    response = repository_server.read_file(str(root), "app.py")
    assert valid(response)["status"] == "ERROR"


@pytest.mark.parametrize("path", ["../original/app.py", "C:/outside.py", "/outside.py"])
def test_path_and_test_selector_escape_rejected(leased, path, monkeypatch):
    root, _, _ = leased
    monkeypatch.setattr(execution_server, "run_tests", lambda *args: pytest.fail("escaped test execution"))
    assert valid(repository_server.read_file(str(root), path))["status"] == "ERROR"
    assert valid(repository_server.apply_patch(str(root), path, "0", "1"))["status"] == "ERROR"
    assert valid(execution_server.run_pytest(str(root), path, 10))["status"] == "ERROR"


def test_leased_read_patch_and_failed_patch_have_consistent_audit(leased):
    root, original, settings = leased
    read = valid(repository_server.read_file(str(root), "app.py"))
    assert read["data"]["content"] == "value = 0\r\n"
    patch = valid(repository_server.apply_patch(str(root), "app.py", "0", "1"))
    assert patch["status"] == "PASS" and "+value = 1" in patch["data"]["patch_diff"]
    assert (root / "app.py").read_bytes() == b"value = 1\r\n"
    rejected = valid(repository_server.apply_patch(str(root), "app.py", "0", "1"))
    assert rejected["status"] == "FAIL" and rejected["error"]["code"] == "PATCH_APPLY_FAILED"
    assert (original / "app.py").read_bytes() == b"value = 0\r\n"
    events = [json.loads(line)["payload"] for line in settings.audit_log.read_text(encoding="utf-8").splitlines()]
    assert [event["status"] for event in events] == ["PASS", "PASS", "FAIL"]
    assert [event["request_id"] for event in events] == [response["metadata"]["request_id"] for response in (read, patch, rejected)]


@pytest.mark.parametrize("status, exit_code, code", [("PASS", 0, None), ("FAIL", 1, "TEST_FAILED"), ("ERROR", None, "TEST_TIMEOUT")])
def test_execution_uses_shared_m2_runner_and_saves_full_evidence(leased, monkeypatch, status, exit_code, code):
    from vgar.contracts.repair import FailureReason
    root, _, _ = leased
    calls = []
    result = RunResult(status=status, command="python -m pytest", argv=["python", "-m", "pytest"],
                       exit_code=exit_code, duration_ms=1500, stdout="完整 output " * 2000,
                       stderr="timeout details" if code == "TEST_TIMEOUT" else "",
                       complete=status != "ERROR", timeout_seconds=10,
                       case_counts={"passed": int(status == "PASS"), "failed": int(status == "FAIL")},
                       reason=FailureReason(code=code, message=code) if code else None)

    def fake(workspace, selectors, timeout):
        calls.append((workspace, selectors, timeout))
        return result

    monkeypatch.setattr(execution_server, "run_tests", fake)
    response = valid(execution_server.run_pytest(str(root), "tests/test_app.py", 10))
    assert calls == [(root, ("tests/test_app.py",), 10)]
    assert response["status"] == status
    data = response["data"] if status != "ERROR" else response["error"]["details"]
    assert data["test_result"] == result.model_dump(mode="json")
    saved = json.loads(Path(data["artifact_path"]).read_text(encoding="utf-8"))
    assert saved["test_result"] == result.model_dump(mode="json")
    assert saved["complete"] and saved["status"] == status


def test_real_execution_emits_junit_case_counts(leased):
    root, _, _ = leased
    response = valid(execution_server.run_pytest(str(root), "tests", 10))
    assert response["status"] == "PASS"
    assert response["data"]["test_result"]["case_counts"]["passed"] == 1
    assert response["data"]["test_result"]["cases"][0]["status"] == "PASS"


def test_link_target_is_rejected_before_read_or_write(leased):
    root, original, _ = leased
    try:
        (root / "linked.py").symlink_to(original / "app.py")
    except OSError:
        pytest.skip("symlink creation unavailable")
    response = repository_server.apply_patch(str(root), "linked.py", "0", "1")
    assert valid(response)["status"] == "ERROR"
    assert (original / "app.py").read_bytes() == b"value = 0\r\n"


def test_workflow_binds_exact_created_workspace(leased):
    import asyncio
    from langchain_core.messages import AIMessage
    from vgar.agents.runtime import Runtime
    from vgar.agents.workflow import run_task
    root, _, settings = leased
    seen = []

    class Agent:
        async def ainvoke(self, payload, config=None):
            return {"messages": [*payload["messages"], AIMessage(content="done")]}

    async def factory(sandboxed):
        seen.append(sandboxed.workspace_root)
        assert sandboxed.workspace_root.is_dir()
        assert sandboxed.workspace_root != root
        return Agent()

    result = asyncio.run(run_task(repo=root, issue_text="fix", selectors=["tests"],
                                 runtime=Runtime(settings=settings, agent_factory=factory)))
    assert len(seen) == 1
    assert not seen[0].exists()


def test_root_symlink_cannot_redirect_lease_to_original(leased):
    root, original, _ = leased
    expired = root.with_name("expired")
    root.rename(expired)
    try:
        root.symlink_to(original, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")
    response = repository_server.apply_patch(str(root), "app.py", "0", "1")
    assert valid(response)["status"] == "ERROR"
    assert (original / "app.py").read_bytes() == b"value = 0\r\n"


def test_oversize_exact_edit_never_writes(leased):
    root, _, _ = leased
    before = (root / "app.py").read_bytes()
    result = repository_server.apply_patch(str(root), "app.py", "0", "x" * (1024 * 1024 + 1))
    assert valid(result)["status"] == "ERROR"
    assert (root / "app.py").read_bytes() == before


def test_selector_inside_lease_cannot_reference_external_symlink(leased, monkeypatch):
    root, original, _ = leased
    try:
        (root / "external_tests").symlink_to(original / "tests", target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")
    monkeypatch.setattr(execution_server, "run_tests", lambda *args: pytest.fail("linked selector executed"))
    assert valid(execution_server.run_pytest(str(root), "external_tests", 10))["status"] == "ERROR"


def test_reparse_root_is_rejected_even_when_symlink_api_reports_false(leased, monkeypatch):
    from types import SimpleNamespace
    root, _, _ = leased
    original = Path.lstat

    def reparse(path):
        return SimpleNamespace(st_file_attributes=0x400) if path == root else original(path)

    monkeypatch.setattr(Path, "lstat", reparse)
    response = repository_server.read_file(str(root), "app.py")
    assert valid(response)["status"] == "ERROR"
