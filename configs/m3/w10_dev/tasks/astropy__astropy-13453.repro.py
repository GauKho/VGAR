"""Issue: Table.write(format='html') ignores the `formats` argument that other ASCII writers respect."""
from io import StringIO

from astropy.table import Table


def test_html_writer_applies_formats():
    t = Table([(1.23875234858e-24, 3.2348748432e-15), (2, 4)], names=('a', 'b'))
    with StringIO() as sp:
        t.write(sp, format='html', formats={'a': lambda x: f'{x:.2e}'})
        html = sp.getvalue()
    assert '1.24e-24' in html and '3.23e-15' in html
    assert '1.23875234858e-24' not in html
