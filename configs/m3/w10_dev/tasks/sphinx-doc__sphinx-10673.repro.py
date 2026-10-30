"""Issue: a toctree listing genindex, modindex and search warns
"toctree contains reference to nonexisting document"; it should be allowed without warnings."""
from io import StringIO

from sphinx.application import Sphinx

INDEX = """Title
=====

.. toctree::
   :maxdepth: 1
   :caption: Indices and tables

   genindex
   modindex
   search
"""


def test_toctree_special_pages_do_not_warn(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'conf.py').write_text('')
    (src / 'index.rst').write_text(INDEX)
    warnings = StringIO()
    app = Sphinx(str(src), str(src), str(tmp_path / 'out'), str(tmp_path / 'doctrees'), 'html',
                 status=None, warning=warnings, freshenv=True)
    app.build()
    assert 'nonexisting document' not in warnings.getvalue()
