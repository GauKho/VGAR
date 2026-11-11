"""Offline preflight consumers. Synthetic unit receipts never close production gates."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/mcp_server/smoke_mcp.py"


def module():
    assert SCRIPT.is_file(), "L6-8 preflight CLI missing"
    spec = importlib.util.spec_from_file_location("preflight_smoke", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_preflight_module_exists():
    module()


@pytest.mark.parametrize("kind", ["empty", "data", "file"])
def test_existing_output_is_preserved(tmp_path, kind):
    m = module()
    out = tmp_path / "old"
    if kind == "file":
        out.write_bytes(b"keep")
    else:
        out.mkdir()
        if kind == "data":
            (out/"keep.json").write_text('{"keep":true}', encoding="utf-8")
    before = out.read_bytes() if out.is_file() else {p.name:p.read_bytes() for p in out.iterdir()}
    with pytest.raises(ValueError, match="exists"):
        m.validate_output(out, inputs=(ROOT/"src",))
    assert (out.read_bytes() if out.is_file() else {p.name:p.read_bytes() for p in out.iterdir()}) == before


def test_output_cannot_overlap_inputs(tmp_path):
    m = module()
    parent = tmp_path / "new-parent"
    with pytest.raises(ValueError, match="overlap"):
        m.validate_output(parent, inputs=(parent/"source",))
    assert not parent.exists()
    with pytest.raises(ValueError):
        m.validate_output(ROOT/"src/unsafe-new-output", inputs=(ROOT/"src",))


@pytest.mark.parametrize("reference", ["../escape.json", "C:/escape.json", "\\\\host\\share\\x", "/absolute", "x/../../escape", "bad. /x"])
def test_receipt_references_are_jailed(tmp_path, reference):
    m = module()
    with pytest.raises(ValueError):
        m.read_receipt(tmp_path, reference)


def test_hash_and_json_failure_are_integrity_errors(tmp_path):
    m = module()
    (tmp_path/"record.json").write_text('{"status":"PASS"}', encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        m.read_receipt(tmp_path, "record.json", expected_hash="sha256:"+"f"*64)
    (tmp_path/"record.json").write_bytes(b"broken")
    with pytest.raises(ValueError):
        m.read_receipt(tmp_path, "record.json")


def observation():
    return {"schema_node_types":["Repository","File","Module","Class","Function","Method","Import","CallSite","Test","Issue"],
            "servers":{"graph":{"registry":[],"graph_jobs":False,"context_factory":False},
                       "execution":{"registry":[],"graph_jobs":False,"context_factory":False}},
            "implementations":{"graph_jobs":True,"legacy_graph":True,"storage":True,
                               "legacy_api_check":True,"legacy_structural_check":True}}


def test_inventory_pass_never_means_providers_ready():
    m = module()
    rows = m.dependency_rows(observation())
    assert rows
    assert any(r["id"] == "bootstrap" and r["owner"] == "TV1" for r in rows)
    assert any(r["id"] == "schema" and "SC-1" in r["tasks"] for r in rows)
    assert any(r["id"] == "verification" and r["owner"] == "TV3" for r in rows)
    assert all(r["evidence"] and r["handoff"] and r["gate"] and r["tv1_integration"] for r in rows)
    build = next(r for r in rows if r["id"] == "build")
    assert build["status"] == "IMPLEMENTED_NOT_BOUND"
    result = m.assess(rows, {"inspector":{"status":"NOT_FOUND_IN_CHECKED_LOCATIONS"},"claude":{"status":"CLI_FOUND"}}, local_checks="PASS")
    assert result["status"] == "PARTIAL" and result["exit_code"] == 2
    assert result["external_host_integration"] == "NOT_RUN"
    assert result["full_chain"] == "NOT_RUN"


def test_synthetic_bound_and_real_bound_remain_unverified():
    m = module()
    observed = observation()
    observed["servers"]["graph"]["registry"] = [{"capabilities":["path"],"synthetic":True,"provider":"unit.Synthetic"}]
    row = next(r for r in m.dependency_rows(observed) if r["id"] == "path")
    assert row["status"] == "SYNTHETIC_ONLY"
    observed["servers"]["graph"]["registry"][0]["synthetic"] = False
    row = next(r for r in m.dependency_rows(observed) if r["id"] == "path")
    assert row["status"] == "BOUND_UNVERIFIED"


def test_broken_observation_does_not_become_dependency():
    m = module()
    bad = observation()
    bad["servers"]["graph"]["registry"] = [{"capabilities":["path"],"synthetic":"false"}]
    with pytest.raises(ValueError):
        m.dependency_rows(bad)


def test_catalog_contains_every_core_tool_resource_and_prompt():
    m = module()
    rows = m.dependency_rows(observation())
    actual = {name for row in rows for name in row["consumers"]}
    oracle = json.loads((ROOT/"tests/fixtures/mcp_server/expected_contract.json").read_text(encoding="utf-8"))
    resources = json.loads((ROOT/"tests/fixtures/mcp_server/resource_contract.json").read_text(encoding="utf-8"))
    assert {r["name"] for r in oracle["core_tools"]} <= actual
    assert set(resources["canonical"]) <= actual
    assert "repair_with_graph_context" in actual


def test_reports_are_deterministic_and_do_not_mutate_inputs():
    m = module()
    rows = m.dependency_rows(observation())
    before = copy.deepcopy(rows)
    assert m.render_dependencies(rows) == m.render_dependencies(rows)
    assert rows == before


def test_preflight_flag_required_and_no_output_on_parse_failure(tmp_path):
    m = module()
    out = tmp_path/"new"
    with pytest.raises(SystemExit):
        m.main(["--client-python","missing", "--server-python","missing", "--output-root",str(out)])
    assert not out.exists()


def test_only_version_help_probes_can_be_run_for_external_clients():
    m = module()
    commands = m.client_probe_commands(Path("C:/Users/pc/.local/bin/claude.exe"))
    assert commands
    assert all(tuple(command[1:]) in {("--version",),("--help",)} for command in commands)


def test_real_default_bootstrap_and_no_grant_probe(tmp_path):
    result = subprocess.run([sys.executable,"-B",str(ROOT/"scripts/mcp_server/_preflight_worker.py"),"probe"],
                            cwd=tmp_path,capture_output=True,timeout=30,check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    observed = json.loads(result.stdout)
    assert observed["servers"]["graph"]["registry"] == []
    assert observed["denials"]["worker_spawned"] is False
    assert observed["denials"]["operation_output_entries"] == 0
    assert observed["denials"]["verification"]["status"] == "NOT_RUN"


def test_observed_rich_schema_does_not_get_reported_as_absent():
    m = module()
    observed = observation()
    observed["schema_node_types"] += ["Component","Port"]
    row = next(r for r in m.dependency_rows(observed) if r["id"] == "schema")
    assert row["status"] == "SCHEMA_PRESENT_UNVERIFIED"


def test_frozen_h1_rank_description_maps_to_public_array_argument():
    m = module()
    m._signature({"properties":{"candidates":{"type":"array"}},"required":["candidates"]},
                 "candidates: RankRequest candidates")
    with pytest.raises(ValueError):
        m._signature({"properties":{"candidates":{"type":"string"}},"required":["candidates"]},
                     "candidates: RankRequest candidates")


def test_graph_producer_pass_without_real_sidecars_is_rejected(tmp_path):
    from dataclasses import asdict

    from vgar.graph.storage_capabilities import legacy_profile
    m = module()
    (tmp_path/"summary.json").write_text('{"status":"PASS","provider":"real-static-builder","fixture_inputs":true}',encoding="utf-8")
    profile = asdict(legacy_profile(resolver_hash="sha256:"+"a"*64,profile_hash="sha256:"+"b"*64))
    profile.pop("validator")
    with pytest.raises(ValueError,match="sidecars/lanes missing"):
        m.consume_graph(tmp_path,profile)


def runtime_stub(tmp_path, *, exit_code=0, duplicate=False):
    """Only a negative consumer fixture, never a runnable provider/acceptance receipt."""
    lane = tmp_path/"2026-07-28-execution"
    lane.mkdir()
    schema = lambda props:{"type":"object","properties":{p:{"type":"string"} for p in props},"required":props}
    tools = [{"name":"health","inputSchema":schema([])},
             {"name":"run_pytest","inputSchema":schema(["selector"])},
             {"name":"run_relevant_tests","inputSchema":schema(["diff"])}]
    if duplicate:
        tools.append(copy.deepcopy(tools[0]))
    wire = {"status":"PASS","protocol":"2026-07-28","tools":tools,"resources":[],"calls":[
        {"tool":"health","response":{"status":"PASS","data":{"server":"execution"},"error":None,"metadata":{"duration_ms":0}}},
        {"tool":"run_pytest","response":{"status":"ERROR","data":None,"error":{"code":"SELECTOR_REJECTED"},"metadata":{"duration_ms":0}}}]}
    (lane/"wire.json").write_text(json.dumps(wire),encoding="utf-8")
    (lane/"command.json").write_text(json.dumps({"complete":True,"exit_code":exit_code}),encoding="utf-8")
    (tmp_path/"runtime-inventory.json").write_text('{"status":"PASS","sdk":"2.2.0","forbidden_packages":[],"forbidden_imports":[]}',encoding="utf-8")
    (tmp_path/"summary.json").write_text(json.dumps({"status":"PASS","wire":[{"server":"execution","requested_mode":"2026-07-28","protocol":"2026-07-28","receipt":"2026-07-28-execution/wire.json"}]}),encoding="utf-8")


def test_boolean_exit_code_is_not_success(tmp_path):
    m = module()
    runtime_stub(tmp_path,exit_code=False)
    with pytest.raises(ValueError,match="Wire command failed"):
        m.consume_runtime(tmp_path)


def test_duplicate_tool_registration_is_integrity_failure(tmp_path):
    m = module()
    runtime_stub(tmp_path,duplicate=True)
    with pytest.raises(ValueError,match="Tool inventory"):
        m.consume_runtime(tmp_path)


def test_execution_receipt_requires_actual_successful_test(tmp_path):
    runtime_stub(tmp_path)
    with pytest.raises(ValueError, match="Missing successful run_pytest"):
        module().consume_runtime(tmp_path)


def test_unknown_called_tool_is_rejected(tmp_path):
    runtime_stub(tmp_path)
    path = tmp_path/"2026-07-28-execution/wire.json"
    wire = json.loads(path.read_bytes())
    wire["calls"][0]["tool"] = "THIS_TOOL_DOES_NOT_EXIST"
    path.write_text(json.dumps(wire),encoding="utf-8")
    with pytest.raises(ValueError, match="Unregistered tool"):
        module().consume_runtime(tmp_path)


def test_legacy_lane_cannot_claim_modern_protocol(tmp_path):
    runtime_stub(tmp_path)
    path = tmp_path/"summary.json"
    value = json.loads(path.read_bytes())
    value["wire"][0]["requested_mode"] = "legacy"
    path.write_text(json.dumps(value),encoding="utf-8")
    with pytest.raises(ValueError, match="Legacy protocol"):
        module().consume_runtime(tmp_path)


def test_blank_graph_resource_receipts_are_rejected():
    with pytest.raises(ValueError, match="resource"):
        module().validate_graph_reads({"resource_reads":[{},{},{}]}, "fixture-symbol")


def test_ignored_prior_seals_are_protected(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m,"ROOT",tmp_path)
    monkeypatch.setattr(m.subprocess,"check_output",lambda *a,**k:b"source.py\0")
    (tmp_path/"source.py").write_bytes(b"keep source")
    (tmp_path/".git").mkdir()
    (tmp_path/".git/index").write_bytes(b"index")
    seal = tmp_path/"results/mcp_server/graph_jobs/previous/artifact_hashes.json"
    seal.parent.mkdir(parents=True)
    seal.write_bytes(b"old seal")
    assert seal.relative_to(tmp_path).as_posix() in m.protected_inputs()


def test_real_fixture_graph_chain_initializes_before_hashing(tmp_path):
    result = subprocess.run([sys.executable,"-B",str(ROOT/"scripts/mcp_server/_preflight_worker.py"),
        "graph","--server-python",sys.executable,"--output-root",str(tmp_path/"graph")],
        cwd=tmp_path,capture_output=True,timeout=120,check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    result = json.loads((tmp_path/"graph/summary.json").read_bytes())
    assert result["status"] == "PASS" and len(result["lanes"]) == 2
