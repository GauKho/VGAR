"""Issue: unused-import is a false positive for a module used only in a type comment."""
from pylint.lint import Run
from pylint.reporters import CollectingReporter

SOURCE = '"""Docstring."""\n\nimport abc\nfrom abc import ABC\n\nX = ...  # type: abc.ABC\nY = ...  # type: ABC\n'


def test_module_used_in_type_comment_is_not_unused(tmp_path):
    module = tmp_path / 'a.py'
    module.write_text(SOURCE)
    reporter = CollectingReporter()
    # No score/report sections: CollectingReporter only collects messages and cannot display layouts.
    Run([str(module), '--disable=all', '--enable=unused-import', '--reports=n', '--score=n'],
        reporter=reporter, exit=False)
    assert [m.symbol for m in reporter.messages] == []
