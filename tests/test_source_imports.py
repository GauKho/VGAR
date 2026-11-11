from vgar.graph.builder import PythonGraphBuilder
from vgar.repair.source_imports import check_source_import_cycles


def measure(root, before, after):
    def build(sources):
        for path, raw in sources.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        return PythonGraphBuilder(repo_key="fixture/source-imports", repository_revision="fixture").build(root)
    baseline = build(before)
    candidate = build(after)
    return check_source_import_cycles(baseline, candidate, before, after)


def test_new_local_import_cycle_has_source_witness(tmp_path):
    before = {"a.py": b"from b import f\n", "b.py": b"def f(): return 1\n"}
    after = {**before, "b.py": b"def f():\n    import a\n    return 1\n"}
    result = measure(tmp_path, before, after)
    assert result.status == "FAIL" and result.reasons == ("NEW_SOURCE_IMPORT_CYCLE",)
    cycle, = result.details["violations"]
    assert cycle["modules"] == ["b", "a", "b"]
    assert cycle["imports"][0][0]["line"] == 2 and cycle["imports"][0][0]["local"]
    assert measure(tmp_path, after, after).status == "PASS"


def test_acyclic_local_import_remains_valid(tmp_path):
    before = {"a.py": b"def f(): return 1\n", "b.py": b"def g(): return 2\n"}
    after = {**before, "a.py": b"def f():\n    import b\n    return b.g()\n"}
    assert measure(tmp_path, before, after).status == "PASS"


def test_relative_local_import_uses_graph_module_identity(tmp_path):
    before = {"pkg/__init__.py": b"", "pkg/a.py": b"def f(): return 1\n",
              "pkg/b.py": b"from .a import f\ndef g(): return f()\n"}
    after = {**before, "pkg/a.py": b"def f():\n    from .b import g\n    return 1\n"}
    assert measure(tmp_path, before, after).status == "FAIL"
