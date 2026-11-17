"""G1 labelled edges (spec 2026-11-16): enumeration, candidates, sampling, sheets, label grammar, lock."""
from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

from vgar.evaluation.g1_labels import (
    Definition,
    Item,
    Label,
    agreement_ids,
    allocate,
    check_agreement,
    check_lock,
    item_to_dict,
    lock,
    parse_label,
    production_files,
    read_sheet,
    run_agreements,
    sample_items,
    scan_repository,
    sha256_file,
    write_agreement_sheet,
    write_sheet,
)

ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _defn(qname, line, kind="function", path="m.py"):
    return Definition(kind, qname, qname.rsplit(".", 1)[-1], path, line, (line,))


def _item(kind="call", repo="r", line=1, path="m.py", col=0, name="f", candidates=None):
    return Item(kind, repo, "t", path, line, col, name, "code", "m", tuple(candidates or [_defn("m.f", 1)]))


# ---- Task 1 ----------------------------------------------------------------------------------------------------

def test_call_and_name_items_at_ast_positions(tmp_path):
    root = _repo(tmp_path, {"pkg/mod.py": "LIMIT = 3\n\ndef helper(x):\n    return x\n\nclass Box:\n    def __init__(self):\n        self.size = LIMIT\n    def grow(self):\n        return helper(self.size)\n"})
    items, stats = scan_repository(root, repo="o/r", task_id="t")
    assert [(i.name, i.line, i.col) for i in items if i.kind == "call"] == [("helper", 10, 15)]
    assert sorted((i.name, i.line) for i in items if i.kind == "name") == [("LIMIT", 8), ("size", 10)]
    assert stats["calls_eligible"] == 1


def test_locals_parameters_and_call_func_are_not_name_items(tmp_path):
    root = _repo(tmp_path, {"m.py": "def f(a):\n    b = a\n    return g(b)\n\ndef g(x):\n    return x\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    assert [i.name for i in items if i.kind == "name"] == []


def test_alias_uses_original_name_for_candidates(tmp_path):
    root = _repo(tmp_path, {"a.py": "def real():\n    return 1\n", "b.py": "from a import real as r\n\ndef use():\n    return r()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call" and i.path == "b.py"]
    assert [c.qualified_name for c in call.candidates] == ["a.real"]


def test_candidates_cover_every_same_name_definition_sorted(tmp_path):
    root = _repo(tmp_path, {"x.py": "class A:\n    def run(self):\n        pass\n", "y.py": "class B:\n    def run(self):\n        pass\n\ndef go(o):\n    o.run()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call"]
    assert [c.qualified_name for c in call.candidates] == ["x.A.run", "y.B.run"]


def test_unparsable_file_is_skipped_and_counted(tmp_path):
    root = _repo(tmp_path, {"ok.py": "def f():\n    return f()\n", "py2.py": "print 'x'\n"})
    items, stats = scan_repository(root, repo="o/r", task_id="t")
    assert stats["unparsed_files"] == ["py2.py"] and len(items) == 1


def test_latin1_file_keeps_raw_byte_columns(tmp_path):
    src = "# -*- coding: latin-1 -*-\ndef f():\n    s = 'é'; return f()\n".encode("latin-1")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "l.py").write_bytes(src)
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = items
    assert call.line == 3 and call.col == len("    s = 'é'; return ".encode("latin-1"))


def test_production_files_skip_tests_conftest_and_setup(tmp_path):
    root = _repo(tmp_path, {"pkg/a.py": "", "tests/test_a.py": "", "conftest.py": "", "setup.py": "", "docs/conf.py": ""})
    assert production_files(root) == ["pkg/a.py"]


# ---- Task 2 ----------------------------------------------------------------------------------------------------

def test_allocate_even_with_remainder_to_largest():
    q = allocate({f"r{i:02d}": 100 + i for i in range(12)}, 150)
    assert sum(q.values()) == 150 and sorted(q.values()) == [12] * 6 + [13] * 6
    assert all(q[f"r{i:02d}"] == 13 for i in range(6, 12))


def test_allocate_redistributes_short_repository():
    q = allocate({"small": 3, **{f"r{i:02d}": 500 for i in range(11)}}, 150)
    assert q["small"] == 3 and sum(q.values()) == 150


def test_sample_is_deterministic_and_respects_quota():
    items = [_item(repo=f"r{n % 3}", line=n) for n in range(90)]
    a, b = sample_items(items, "call", 30, seed=0), sample_items(items, "call", 30, seed=0)
    assert a == b and Counter(i.repo for i in a) == {"r0": 10, "r1": 10, "r2": 10}


def test_parse_label_grammar():
    cands = (_defn("a.f", 1), _defn("b.f", 2), _defn("c.f", 3))
    assert parse_label(" 1 ; 3 ", cands).targets == (cands[0], cands[2])
    assert parse_label(" External ", cands).cls == "external"
    assert parse_label("other:pkg.mod.g", cands) == Label("in_repo", ("pkg.mod.g",))
    for bad in ("", "4", "1, 3", "maybe"):
        with pytest.raises(ValueError):
            parse_label(bad, cands)


def _kit_out(tmp_path):
    out = tmp_path / "kit"
    out.mkdir()
    calls = [_item(line=1), _item(line=2)]
    names = [_item("name", line=3), _item("name", line=4)]
    write_sheet(out / "calls.csv", calls, "C")
    write_sheet(out / "name_uses.csv", names, "N")
    (out / "manifest.json").write_text(json.dumps({"locks": []}), encoding="utf-8")
    return out, {**{f"C{n:03d}": i for n, i in enumerate(calls, 1)}, **{f"N{n:03d}": i for n, i in enumerate(names, 1)}}


def _fill(path, labels):
    rows = list(read_sheet(path).values())
    for row in rows:
        row["label"] = labels.get(row["item_id"], row["label"])
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_lock_refuses_invalid_and_detects_edits(tmp_path):
    out, items = _kit_out(tmp_path)
    _fill(out / "calls.csv", {"C001": "1", "C002": ""})
    with pytest.raises(ValueError, match="C002"):
        lock(out, items)
    _fill(out / "calls.csv", {"C002": "builtin"})
    _fill(out / "name_uses.csv", {"N001": "unknown", "N002": "1"})
    lock(out, items)
    check_lock(out, "calls.csv")
    _fill(out / "calls.csv", {"C001": "unknown"})
    with pytest.raises(ValueError):
        check_lock(out, "calls.csv")


def test_agreement_sheet_hides_claude_labels(tmp_path):
    out, _ = _kit_out(tmp_path)
    _fill(out / "calls.csv", {"C001": "1"})
    ids = agreement_ids(["C001", "C002"], ["N001", "N002"], k=1, seed=1)
    main = {**read_sheet(out / "calls.csv"), **read_sheet(out / "name_uses.csv")}
    write_agreement_sheet(out / "agreement_user.csv", main, ids)
    rows = read_sheet(out / "agreement_user.csv")
    assert sorted(rows) == sorted(ids) and all(r["label"] == "" for r in rows.values())
    assert agreement_ids(["C001", "C002"], ["N001", "N002"], k=1, seed=1) == ids


# ---- Task 4 ----------------------------------------------------------------------------------------------------

def _load_kit():
    spec = importlib.util.spec_from_file_location("g1_label_kit", ROOT / "scripts" / "g1_label_kit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_tasks_first_per_repository():
    kit = _load_kit()
    rows = [{"repo": "a/x", "instance_id": "1"}, {"repo": "b/y", "instance_id": "2"}, {"repo": "a/x", "instance_id": "3"}]
    assert [r["instance_id"] for r in kit.select_tasks(rows)] == ["1", "2"]


def test_kit_writes_sheets_from_local_trees(tmp_path, monkeypatch):
    kit = _load_kit()
    source = "def helper(x):\n    return x\n\nLIMIT = 1\n\ndef a():\n    helper(1)\n    helper(2)\n    helper(3)\n    return LIMIT + LIMIT\n"

    def fake_read(row, cache_root, network=True):
        archive = tmp_path / f"{row['instance_id']}.tar.gz"
        archive.write_bytes(row["instance_id"].encode())
        return {}, {"cache_path": str(archive)}

    def fake_extract(archive, repo, commit, destination):
        (Path(destination)).mkdir(parents=True, exist_ok=True)
        (Path(destination) / "m.py").write_text(source, encoding="utf-8")

    monkeypatch.setattr(kit, "read_repository_sources", fake_read)
    monkeypatch.setattr(kit, "extract_python_tree", fake_extract)
    manifest = tmp_path / "gold.json"
    manifest.write_text(json.dumps({"manifest_hash": "h", "tasks": [
        {"repo": "o/a", "instance_id": "a-1", "base_commit": "c1"}, {"repo": "o/b", "instance_id": "b-1", "base_commit": "c2"}]}), encoding="utf-8")
    out = tmp_path / "out"
    kit.main(["--root", str(tmp_path), "--manifest", str(manifest), "--out", str(out), "--calls", "4", "--names", "2"])
    assert {p.name for p in out.iterdir()} >= {"calls.csv", "name_uses.csv", "items.md", "items.json", "agreement_user.csv", "manifest.json"}
    meta = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(read_sheet(out / "calls.csv")) == 4 and len(read_sheet(out / "name_uses.csv")) == 2 and meta["locks"] == []
    assert "graph" not in (out / "items.md").read_text(encoding="utf-8").lower()
    assert item_to_dict  # items.json round-trips through item_to_dict / item_from_dict


# ---- Task 3 ----------------------------------------------------------------------------------------------------

from vgar.evaluation.g1_labels import (
    READS_RULE,
    GraphIndex,
    Scored,
    agreement,
    bom_adjusted,
    micro_pr,
    score_item,
)


def _node(node_id, kind, name, path, start, end, qname=None, start_col=0, properties=None):
    return {"id": node_id, "type": kind, "name": name, "qualified_name": qname or name, "path": path,
            "range": {"start_line": start, "start_col": start_col, "end_line": end, "end_col": 0},
            "properties": properties or {}}


def _edge(kind, source, target, rule="python.call.static.resolve.v1"):
    return {"type": kind, "source_id": source, "target_id": target, "provenance": {"rule_id": rule}}


def _doc(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def _doc_call():
    return _doc([_node("F", "Function", "f", "m.py", 1, 2, "m.f"), _node("G", "Function", "g", "m.py", 3, 4, "m.g"),
                 _node("CS", "CallSite", "f", "m.py", 10, 10, start_col=15)],
                [_edge("CALLS", "CS", "F"), _edge("MAY_CALL", "CS", "G", "python.call.may_call.name.v1")])


def _doc_property():
    return _doc([_node("X_GET", "Method", "x", "c.py", 3, 4, "c.C.x"), _node("X_SET", "Method", "x", "c.py", 6, 7, "c.C.x")], [])


def _doc_reads():
    return _doc([_node("FN", "Function", "f", "m.py", 7, 9, "m.f"),
                 _node("FIELD_SIZE", "Field", "size", "m.py", 5, 5, "m.Box.size", properties={"assignment_lines": [5]}),
                 _node("G_LIMIT", "GlobalVariable", "LIMIT", "m.py", 1, 1, "m.LIMIT")],
                [_edge("REFERENCES", "FN", "FIELD_SIZE", READS_RULE), _edge("REFERENCES", "FN", "G_LIMIT", "other.rule")])


def _scored(truth, predicted):
    return Scored("i", "call", "r", Label("in_repo", ()), set(truth), set(predicted), "right", 0)


def test_callsite_matched_by_position_and_may_call_separate():
    idx = GraphIndex(_doc_call())
    found, calls, both = idx.call_targets(_item(kind="call", path="m.py", line=10, col=15))
    assert found and calls == {"F"} and both == {"F", "G"}
    assert idx.call_targets(_item(kind="call", path="m.py", line=10, col=16))[0] is False


def test_same_name_definitions_map_by_line():
    idx = GraphIndex(_doc_property())
    assert idx.node_for(_defn("c.C.x", 3, kind="method", path="c.py")) == "X_GET"
    assert idx.node_for(_defn("c.C.x", 6, kind="method", path="c.py")) == "X_SET"


def test_name_targets_use_reads_rule_and_name():
    idx = GraphIndex(_doc_reads())
    assert idx.name_targets(_item(kind="name", path="m.py", line=8, name="size")) == {"FIELD_SIZE"}
    assert idx.name_targets(_item(kind="name", path="m.py", line=8, name="LIMIT")) == set()


def test_micro_pr_hand_computed():
    rows = [_scored({"A"}, {"A"}), _scored({"A", "B"}, {"A"}), _scored(set(), {"C"}), _scored({"D"}, set())]
    r = micro_pr(rows)
    assert (r["tp"], r["fp"], r["fn"]) == (2, 1, 2)
    assert r["precision"] == pytest.approx(2 / 3) and r["recall"] == pytest.approx(2 / 4)


def test_unmapped_target_counts_as_miss():
    s = score_item(GraphIndex(_doc_call()), "C001", _item(kind="call", path="m.py", line=10, col=15),
                   Label("in_repo", ("nowhere.h",)))
    assert s.unmapped == 1 and "unmapped:nowhere.h" in s.truth and s.status == "wrong"


def test_agreement_raw_and_kappa():
    c = {"1": Label("in_repo", (_defn("a.f", 1),)), "2": Label("external", ()), "3": Label("builtin", ()),
         "4": Label("in_repo", (_defn("a.g", 2),))}
    u = {"1": Label("in_repo", (_defn("a.f", 1),)), "2": Label("external", ()), "3": Label("external", ()),
         "4": Label("in_repo", (_defn("a.h", 3),))}
    a = agreement(c, u)
    assert a["raw"] == 0.5 and a["disagreements"] == ["3", "4"]
    assert a["kappa"] == pytest.approx((0.75 - 0.375) / (1 - 0.375))
    assert agreement({"1": Label("unknown", ())}, {"1": Label("unknown", ())})["kappa"] is None


# ---- Task 5 ----------------------------------------------------------------------------------------------------

EVAL_SOURCE = "LIMIT = 1\n\ndef helper(x):\n    return x\n\ndef a():\n    helper(1)\n    return helper(LIMIT)\n"


def _load_eval():
    spec = importlib.util.spec_from_file_location("g1_evaluate", ROOT / "scripts" / "g1_evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _locked_kit(tmp_path, monkeypatch, user_labels=None):
    kit = _load_kit()

    def fake_read(row, cache_root, network=True):
        archive = tmp_path / "a.tar.gz"
        archive.write_bytes(b"archive")
        return {}, {"cache_path": str(archive)}

    def fake_extract(archive, repo, commit, destination):
        Path(destination).mkdir(parents=True, exist_ok=True)
        (Path(destination) / "m.py").write_text(EVAL_SOURCE, encoding="utf-8")

    monkeypatch.setattr(kit, "read_repository_sources", fake_read)
    monkeypatch.setattr(kit, "extract_python_tree", fake_extract)
    manifest = tmp_path / "gold.json"
    manifest.write_text(json.dumps({"tasks": [{"repo": "o/a", "instance_id": "a-1", "base_commit": "c1"}]}), encoding="utf-8")
    out = tmp_path / "kit"
    kit.main(["--root", str(tmp_path), "--manifest", str(manifest), "--out", str(out), "--calls", "2", "--names", "1"])
    _fill(out / "calls.csv", {"C001": "1", "C002": "1"})
    _fill(out / "name_uses.csv", {"N001": "1"})
    kit.main(["--out", str(out), "--lock"])
    if user_labels:
        rows = read_sheet(out / "agreement_user.csv")
        _fill(out / "agreement_user.csv", {i: ("1" if user_labels == "agree" or i.startswith("N") else "unknown") for i in rows})
    return out


def test_evaluator_refuses_unlocked_or_edited_sheets(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch)
    _fill(kit_dir / "calls.csv", {"C001": "unknown"})
    assert _load_eval().main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 2


def test_evaluator_stops_for_unsettled_disagreements(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="disagree")
    assert _load_eval().main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 3
    assert (kit_dir / "disagreements.csv").exists()


def test_evaluator_static_report_on_fixture(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="agree")
    assert _load_eval().main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 0
    report = json.loads((tmp_path / "o" / "g1_report.json").read_text(encoding="utf-8"))
    static = report["configurations"]["static"]
    assert static["calls"]["calls_only"]["n"] == 2 and static["calls"]["calls_only"]["recall"] == 1.0
    assert report["configurations"]["tsg"]["status"] == "not run: no --tsg-executable"
    assert report["agreement"]["raw"] == 1.0
    md = (tmp_path / "o" / "g1_report.md").read_text(encoding="utf-8")
    assert md.startswith("# G1") and "Labels assigned by Claude" in md


# ---- final review fixes ----------------------------------------------------------------------------------------

def _graph(root):
    from vgar.graph.builder import PythonGraphBuilder
    return PythonGraphBuilder(repo_key="o/r", repository_revision="r").build(root)


def test_chained_call_matches_its_own_callsite(tmp_path):
    root = _repo(tmp_path, {"m.py": "class C:\n    def helper(self):\n        return self\n    def run(self):\n        return 1\n    def go(self):\n        return self.helper().run()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (run,) = [i for i in items if i.kind == "call" and i.name == "run"]
    idx = GraphIndex(_graph(root))
    found, calls, _ = idx.call_targets(run)
    assert found and {idx.nodes[c]["name"] for c in calls} <= {"run"}


def test_bom_file_columns_match_graph(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "m.py").write_bytes(b"\xef\xbb\xbfdef f():\n    return 1\n\ndef g():\n    return f()\n")
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call"]
    assert GraphIndex(_graph(root)).call_targets(bom_adjusted(call, root))[0] is True


def test_merged_definition_maps_to_every_node(tmp_path):
    root = _repo(tmp_path, {"m.py": "import sys\n\nif sys.version_info > (3,):\n    def f():\n        return 1\nelse:\n    def f():\n        return 2\n\ndef g():\n    return f()\n"})
    items, _ = scan_repository(root, repo="o/r", task_id="t")
    (call,) = [i for i in items if i.kind == "call" and i.name == "f"]
    assert len(call.candidates) == 1 and len(call.candidates[0].lines) == 2
    s = score_item(GraphIndex(_graph(root)), "C001", call, Label("in_repo", (call.candidates[0],)))
    assert s.unmapped == 0 and len(s.truth) == 1 and s.truth <= s.predicted


def test_name_outside_function_has_its_own_status():
    s = score_item(GraphIndex(_doc_reads()), "N001", _item(kind="name", path="m.py", line=20, name="size"),
                   Label("in_repo", (_defn("m.Box.size", 5, kind="field"),)))
    assert s.status == "outside_function"


def test_evaluator_refuses_partial_agreement(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch)
    first = next(iter(read_sheet(kit_dir / "agreement_user.csv")))
    _fill(kit_dir / "agreement_user.csv", {first: "1"})
    rows = read_sheet(kit_dir / "agreement_user.csv")
    if len(rows) > 1:
        assert _load_eval().main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 2


def test_evaluator_refuses_agreement_edited_after_first_use(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="disagree")
    ev = _load_eval()
    assert ev.main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 3
    _fill(kit_dir / "agreement_user.csv", {i: "1" for i in read_sheet(kit_dir / "agreement_user.csv")})
    assert ev.main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 2


def test_evaluator_refuses_settlement_outside_disagreements(tmp_path, monkeypatch):
    kit_dir = _locked_kit(tmp_path, monkeypatch, user_labels="agree")
    with open(kit_dir / "settlement.csv", "w", encoding="utf-8", newline="") as handle:
        handle.write("item_id,final_label\nC001,unknown\n")
    assert _load_eval().main(["--kit", str(kit_dir), "--out", str(tmp_path / "o")]) == 2


# ---- Plan 2026-11-17 Task 2: a second agreement sheet (human) --------------------------------------------------

def _kit_with_agreement(tmp_path):
    out, items = _kit_out(tmp_path)
    _fill(out / "calls.csv", {"C001": "1", "C002": "builtin"})
    _fill(out / "name_uses.csv", {"N001": "unknown", "N002": "1"})
    lock(out, items)
    main = {**read_sheet(out / "calls.csv"), **read_sheet(out / "name_uses.csv")}
    for sheet in ("agreement_user.csv", "agreement_human.csv"):
        write_agreement_sheet(out / sheet, main, ["C001", "N002"])
    _fill(out / "agreement_user.csv", {"C001": "1", "N002": "1"})
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    manifest["agreement_lock"] = sha256_file(out / "agreement_user.csv")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out, items, main


def _check(out, items, main, sheet):
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    labels = {i: parse_label(r["label"], items[i].candidates) for i, r in main.items()}
    return check_agreement(out, sheet, manifest, items, labels, main)


def test_human_sheet_locks_separately_and_keeps_user_lock(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_human.csv", {"C001": "1", "N002": "1"})
    before = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["agreement_lock"]
    result = _check(out, items, main, "agreement_human.csv")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert result.exit_code is None and result.report["agreement_source"] == "human"
    assert manifest["agreement_lock"] == before
    assert manifest["agreement_locks"]["agreement_human.csv"] == sha256_file(out / "agreement_human.csv")


def test_human_sheet_disagreements_use_own_files(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_human.csv", {"C001": "external", "N002": "1"})
    result = _check(out, items, main, "agreement_human.csv")
    assert result.exit_code == 3
    assert (out / "disagreements_agreement_human.csv").exists() and not (out / "disagreements.csv").exists()


def test_human_sheet_settlement_changes_final_label(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_human.csv", {"C001": "external", "N002": "1"})
    _check(out, items, main, "agreement_human.csv")
    (out / "settlement_agreement_human.csv").write_text("item_id,final_label\nC001,external\n", encoding="utf-8")
    result = _check(out, items, main, "agreement_human.csv")
    assert result.exit_code is None and result.report["settlement"]["changed"] == ["C001"]
    assert result.labels["C001"].cls == "external"


def test_human_sheet_edit_after_first_use_is_refused(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_human.csv", {"C001": "1", "N002": "1"})
    _check(out, items, main, "agreement_human.csv")
    _fill(out / "agreement_human.csv", {"C001": "external"})
    assert _check(out, items, main, "agreement_human.csv").exit_code == 2


@pytest.mark.parametrize("sheet", ["agreement_human2.csv", "../agreement_human.csv", "./agreement_user.csv", "x/a.csv"])
def test_only_the_two_known_sheet_names_are_accepted(tmp_path, sheet):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_human.csv", {"C001": "1", "N002": "1"})
    assert _check(out, items, main, sheet).exit_code == 2


def test_sheet_name_case_maps_to_known_sheet(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    assert _check(out, items, main, "AGREEMENT_USER.csv").report["agreement_source"] == "claude_second_pass"


def test_human_run_keeps_the_default_sheet_settlement(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    _fill(out / "agreement_user.csv", {"C001": "external", "N002": "1"})      # Claude 2nd pass differs on C001
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    manifest["agreement_lock"] = sha256_file(out / "agreement_user.csv")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (out / "settlement.csv").write_text("item_id,final_label\nC001,external\n", encoding="utf-8")
    _fill(out / "agreement_human.csv", {"C001": "1", "N002": "1"})            # human agrees with Claude's main label
    labels = {i: parse_label(r["label"], items[i].candidates) for i, r in main.items()}
    result = run_agreements(out, "agreement_human.csv", json.loads((out / "manifest.json").read_text()), items, labels, main)
    assert result.exit_code is None and result.labels["C001"].cls == "external"
    assert result.report["agreement_source"] == "human" and result.report["default_settlement"]["changed"] == ["C001"]
    assert result.report["agreement"]["disagreements"] == []                  # compared with Claude's own labels


def test_default_sheet_behaviour_unchanged(tmp_path):
    out, items, main = _kit_with_agreement(tmp_path)
    result = _check(out, items, main, "agreement_user.csv")
    assert result.exit_code is None and result.report["agreement_source"] == "claude_second_pass"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert result.report["agreement"]["n"] == 2 and "agreement_locks" not in manifest
