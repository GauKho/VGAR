"""Reproduction written from the issue text only (pyreverse ignores type hints when the default is None).

Uses the pyreverse API present at the base commit: project_from_files -> Linker -> ClassDiagram.get_attrs,
which renders an attribute as "name : Type1, Type2".
"""
from pylint.pyreverse.diagrams import ClassDiagram
from pylint.pyreverse.inspector import Linker, project_from_files

SOURCE = '''
class C(object):
    def __init__(self, a: str = None):
        self.a = a
'''


def test_type_hint_shown_for_none_default(tmp_path, monkeypatch):
    module = tmp_path / "vgar_w9_hinted.py"
    module.write_text(SOURCE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))  # astroid names the module from sys.path
    project = project_from_files([str(module)], project_name="vgar_w9")
    Linker(project).visit(project)
    klass = project.get_module("vgar_w9_hinted")["C"]
    attrs = ClassDiagram("classes", "ALL").get_attrs(klass)
    [rendered] = [a for a in attrs if a.split(" : ")[0] == "a"]
    types = rendered.split(" : ", 1)[1].split(", ") if " : " in rendered else []
    assert "str" in types, rendered
