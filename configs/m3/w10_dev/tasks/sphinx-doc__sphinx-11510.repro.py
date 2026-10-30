"""Issue: changes a source-read handler makes to an include'd file never reach the built HTML."""
from sphinx.application import Sphinx

INDEX = 'This is a test\n==============\n\n.. include:: something-to-include.rst\n\n&REPLACE_ME;\n'
INCLUDED = 'Testing\n=======\n\n&REPLACE_ME;\n'


def replace(app, docname, source):
    source[0] = source[0].replace('&REPLACE_ME;', 'REPLACED')


def test_source_read_applies_to_included_files(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'conf.py').write_text('')
    (src / 'index.rst').write_text(INDEX)
    (src / 'something-to-include.rst').write_text(INCLUDED)
    app = Sphinx(str(src), str(src), str(tmp_path / 'out'), str(tmp_path / 'doctrees'), 'html',
                 status=None, warning=None, freshenv=True)
    app.connect('source-read', replace)
    app.build()
    html = (tmp_path / 'out' / 'index.html').read_text()
    assert 'REPLACE_ME' not in html
