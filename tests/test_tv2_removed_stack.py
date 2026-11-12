"""The repo serves MCP servers only: removed stacks (LangChain agents, real generator, repair server) stay gone.

Spec: docs/superpowers/specs/2026-11-12-remove-langchain-sdk2-design.md
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCKED = ("langchain", "langchain_core", "langgraph", "langchain_mcp_adapters", "langchain_huggingface")
REMOVED = ("vgar.agents", "vgar.mcp.client", "vgar.models.factory", "hf_model", "local_hf_chat_model",
           "langchain", "langgraph", "create_mcp_client")
# Task 3: the real Qwen generator and its ML stack are gone; only mode "fake" remains.
REMOVED += ("generator_hf", "hf_backend", "hf_worker", "model_worker", "hf_diagnostics", "HFGenerator", "HFChatTokenizer")
BLOCKED += ("torch", "transformers", "accelerate", "peft", "trl", "datasets")
# Task 4: the coding agent (Claude Code, OpenCode) edits code itself, so repair_server is gone.
REMOVED += ("repair_server", '"vgar-repair"')  # the server key, not schema ids like vgar-repair-admission-v1
# Task 7: the M2 patch-generation engine and its experiment campaign (spec §4.1b); verification tools stay.
REMOVED += ("vgar.repair.pipeline", "vgar.repair.session", "vgar.repair.prompt", "vgar.repair.failure", "vgar.models",
            "evaluation.repair.launch", "evaluation.repair.runner", "evaluation.repair.gpu", "evaluation.repair.preflight",
            "evaluation.repair.aggregate", "evaluation.repair.derive_config", "evaluation.dry_run")
# Kept on purpose (2-week plan, TV1 week 2): harness.candidates + grade_repair_candidates.py grade patches with the
# official SWE-bench harness, agent_metrics + aggregate_agent_traces.py measure MCP usability from the audit log.
# TV1's runtime gate checks that a venv has no LangChain; naming it there is the point.
_ALLOWED = {f"scripts/mcp_server/{name}.py": ("langchain",) for name in ("check_runtime", "_runtime_probe", "smoke_mcp")}
_ALLOWED = {path: ("langchain", "langgraph") for path in _ALLOWED}
_ALLOWED["scripts/mcp_server/_runtime_probe.py"] += ("vgar.mcp.client",)  # asserts the legacy client is not imported


def _allowed(path: Path, line: str) -> bool:
    names = _ALLOWED.get(path.relative_to(ROOT).as_posix(), ())
    return any(name in line for name in names) and not any(r in line for r in REMOVED if r not in names)


def test_no_reference_to_removed_modules():
    files = [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/**/*.py")]
    hits = [f"{p.relative_to(ROOT).as_posix()}:{n}: {line.strip()}"
            for p in files if "__pycache__" not in p.parts
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if any(name in line for name in REMOVED) and not _allowed(p, line)]
    assert hits == []


def test_every_vgar_module_imports_without_blocked_packages():
    code = textwrap.dedent(f"""
        import importlib, pkgutil, sys
        for name in {BLOCKED!r}:
            sys.modules[name] = None
        import vgar
        bad = []
        for info in pkgutil.walk_packages(vgar.__path__, "vgar."):
            try:
                importlib.import_module(info.name)
            except ImportError as error:
                text = str(error)
                if any(name in text for name in {BLOCKED!r}) or any(name in text for name in {REMOVED!r}):
                    bad.append(info.name + ": " + text)
        print("\\n".join(bad), file=sys.stderr)
        sys.exit(1 if bad else 0)
    """)
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=600)
    assert result.returncode == 0, result.stderr[-4000:]


def test_templates_list_exactly_three_servers():
    for name in ("claude-code", "inspector-legacy", "inspector-modern"):
        servers = json.loads((ROOT / f"configs/mcp_server/{name}.template.json").read_text(encoding="utf-8"))["mcpServers"]
        assert set(servers) == {"vgar-graph", "vgar-repository", "vgar-execution"}, name
    runtime = json.loads((ROOT / "configs/mcp_server/runtime.json").read_text(encoding="utf-8"))
    assert set(runtime["entrypoints"]) == {"graph", "repository", "execution"}
    assert set(runtime["operator_bindings"]) == {"graph", "repository", "execution", "all"}
    assert not (ROOT / "src/vgar/mcp/servers/repair_server.py").exists()


def test_pyproject_dependencies_match_the_spec():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {re.split(r"[<>=\[ ]", d, maxsplit=1)[0].lower() for d in project["dependencies"]}
    assert names == {"mcp", "pydantic", "packaging", "filelock", "python-dotenv", "tree-sitter",
                     "tree-sitter-python", "pyyaml", "tokenizers", "jinja2", "pyarrow"}
    assert "mcp==2.2.0" in project["dependencies"]
    assert set(project["optional-dependencies"]) == {"dev", "history", "plot", "code-graph"}


def test_verification_tools_survive():
    import hashlib
    import importlib

    for name in ("mutant_pool", "verifier_eval", "fairness", "manifest", "prompt_fingerprint"):
        importlib.import_module(f"vgar.evaluation.repair.{name}")
    from vgar.evaluation.repair.prompt_fingerprint import template_path
    from vgar.repair.deadline import DeadlineExecutor, StopRun, require_trusted_fixture  # noqa: F401

    path = template_path("m2-w78-v11")
    assert path == ROOT / "src/vgar/evaluation/repair/prompts/repair_v11.txt"
    head = subprocess.run(["git", "show", "HEAD:src/vgar/agents/prompts/repair_v11.txt"], cwd=ROOT,
                          capture_output=True, check=True).stdout
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(head).digest()


def test_settings_have_no_model_or_agent_section():
    from dataclasses import fields

    import vgar.config as config
    from vgar.config.settings import Settings

    assert {f.name for f in fields(Settings)} == {"graph", "audit_log"}
    assert not hasattr(config, "ModelSettings") and not hasattr(config, "AgentSettings")


def test_tv1_runtime_probe_imports_only_existing_servers():
    # The probe builds server module names with an f-string, which the literal scan cannot see.
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/mcp_server/_runtime_probe.py")],
                            capture_output=True, text=True, cwd=ROOT, timeout=300,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    assert result.returncode == 0, result.stderr[-2000:]
    assert json.loads(result.stdout)["status"] == "PASS"


def test_ci_workflow_runs_only_existing_scripts_and_installs_the_extras_tests_need():
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for script in re.findall(r"python (scripts/[\w/]+\.py)", text):
            assert (ROOT / script).is_file(), f"{workflow.name}: {script}"
        if "pip install -e" in text:
            assert "code-graph" in text and "torch" not in text, workflow.name
