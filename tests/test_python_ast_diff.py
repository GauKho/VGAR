import pytest

from vgar.graph.ast_diff import diff_python_ast


def test_shipping_threshold_matches_the_single_case_oracle():
    before = (
        b"FREE_SHIPPING_THRESHOLD = 50_000\n\ndef shipping_fee(subtotal: int) -> int:\n"
        b"    if subtotal > FREE_SHIPPING_THRESHOLD:\n        return 0\n    return 5_000\n"
    )
    after = before.replace(b"subtotal > FREE_SHIPPING_THRESHOLD", b"subtotal >= FREE_SHIPPING_THRESHOLD")
    result = diff_python_ast(before, after)
    edit, = result.edits
    assert (edit.symbol, edit.change, edit.changed_parts) == ("shipping_fee", "MODIFIED", ("body",))
    assert (edit.before[0].start_line, edit.before[0].end_line) == (3, 6)
    assert edit.before == edit.after and not result.module_statements_changed


def test_declaration_and_body_edits_have_qualified_names_and_spans():
    before = b"""class Service:
    @cached
    async def run(self, timeout=1):
        return 1

def removed():
    pass
"""
    after = b"""class Service:
    @cached
    async def run(self, timeout=2):
        return 1

def added():
    pass
"""
    result = diff_python_ast(before, after)
    method, added, removed = result.edits
    assert (method.symbol, method.change, method.changed_parts) == ("Service.run", "MODIFIED", ("declaration",))
    assert method.before[0].kind == "async_function" and method.before[0].start_line == 2
    assert (added.symbol, added.change, added.before) == ("added", "ADDED", ())
    assert (removed.symbol, removed.change, removed.after) == ("removed", "REMOVED", ())
    assert not result.module_statements_changed


def test_formatting_preserves_ast_and_non_definition_statements_are_compared():
    before = b"VALUE = 1  # type: ignore[name-defined]\n\ndef f():\n    return VALUE\n"
    reformatted = b"# Comment\nVALUE=1  # type: ignore[name-defined]\n\ndef f(): return (VALUE)\n"
    same = diff_python_ast(before, reformatted)
    assert same.edits == () and not same.module_statements_changed
    constant = diff_python_ast(before, before.replace(b"VALUE = 1", b"VALUE = 2"))
    assert [(e.symbol, e.change) for e in constant.edits] == [("VALUE", "MODIFIED")]
    assert not constant.module_statements_changed  # a plain-name assignment is a global edit (L4-4 fix)
    assert diff_python_ast(before, before.replace(b"name-defined", b"assignment")).module_statements_changed


def test_repeated_definitions_are_compared_in_source_order():
    before = b"def f(a): return 1\ndef f(a): return 2\n"
    edit, = diff_python_ast(before, before.replace(b"return 1", b"return 3")).edits
    assert edit.change == "MODIFIED" and edit.changed_parts == ("body",)
    assert [span.start_line for span in edit.before] == [1, 2]
    assert [span.start_line for span in edit.after] == [1, 2]


def test_detects_when_a_definition_moves_across_a_module_statement():
    before = b"def f(): return 1\nVALUE = f()\n"
    after = b"VALUE = f()\ndef f(): return 1\n"
    result = diff_python_ast(before, after)
    assert not result.edits and result.module_statements_changed


def test_detects_class_execution_order_and_keeps_method_additions_local():
    before = b"class C:\n    def f(): return 1\n    value = f()\n"
    after = b"class C:\n    value = f()\n    def f(): return 1\n"
    edit, = diff_python_ast(before, after).edits
    assert (edit.symbol, edit.changed_parts) == ("C", ("body",))
    added, = diff_python_ast(before, before + b"    def g(): return 2\n").edits
    assert (added.symbol, added.change) == ("C.g", "ADDED")


def test_syntax_failure_preserves_the_failing_version_path():
    with pytest.raises(SyntaxError) as exc:
        diff_python_ast(None, b"def f(:\n", after_path="src/broken.py")
    assert exc.value.filename == "src/broken.py"


# --- L4-4 fixes (14/11): docstrings, module-level names, parse errors per file ---

def test_docstring_only_change_is_its_own_part():
    before = b'def f():\n    """Old."""\n    return 1\n'
    edit, = diff_python_ast(before, before.replace(b"Old.", b"New.")).edits
    assert (edit.symbol, edit.change, edit.changed_parts) == ("f", "MODIFIED", ("docstring",))


def test_docstring_and_code_change_is_body():
    before = b'class C:\n    """Old."""\n    x = 1\n'
    edit, = diff_python_ast(before, b'class C:\n    """New."""\n    x = 2\n').edits
    assert edit.changed_parts == ("body",)


def test_module_docstring_change_is_not_module_statement():
    result = diff_python_ast(b'"""A."""\nimport os\n', b'"""B."""\nimport os\n')
    assert result.edits == () and not result.module_statements_changed


def test_module_constant_change_is_a_global_edit():
    result = diff_python_ast(b"LIMIT = 1\nimport os\n", b"LIMIT = 2\nNEW: int = 3\nimport os\n")
    assert [(e.symbol, e.change, (e.before or e.after)[0].kind) for e in result.edits] == \
        [("LIMIT", "MODIFIED", "global"), ("NEW", "ADDED", "global")]
    assert not result.module_statements_changed


def test_moving_a_global_across_code_is_a_module_statement_change():
    result = diff_python_ast(b"import os\nA = 1\n", b"A = 1\nimport os\n")
    assert result.edits == () and result.module_statements_changed


def test_tuple_targets_stay_module_statements():
    result = diff_python_ast(b"a, b = 1, 2\n", b"a, b = 1, 3\n")
    assert result.edits == () and result.module_statements_changed


def test_parse_error_in_one_file_keeps_other_files(tmp_path):
    from git_fixture import linear_repo

    from vgar.graph.ast_diff import diff_python_commit
    from vgar.graph.history import read_commit_history

    ids = linear_repo(tmp_path / "r", [
        ("base", {"old.py": b"x = 1\n", "good.py": b"def f():\n    return 1\n"}),
        ("change", {"old.py": b"print 'x'\n", "good.py": b"def f():\n    return 2\n"}),
    ])
    window = read_commit_history(tmp_path / "r", revision=ids[-1], max_commits=1)
    diffs = {d.after.path: d for d in diff_python_commit(tmp_path / "r", window.commits[0])}
    assert diffs["old.py"].parse_error.side == "after" and diffs["old.py"].ast_diff.edits == ()
    assert diffs["good.py"].parse_error is None and diffs["good.py"].ast_diff.edits
