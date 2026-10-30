"""Issue: --setup-show with a bytes parameter raises BytesWarning under `python -bb` (str() of bytes)."""
import subprocess
import sys

TEST = "import pytest\n\n@pytest.mark.parametrize('data', [b'Hello World'])\ndef test_data(data):\n    pass\n"


def test_setup_show_with_bytes_parameter_has_no_bytes_warning(tmp_path):
    (tmp_path / 'test_bytes.py').write_text(TEST)
    result = subprocess.run([sys.executable, '-bb', '-m', 'pytest', '--setup-show', '-p', 'no:cacheprovider',
                             str(tmp_path / 'test_bytes.py')], cwd=str(tmp_path),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    assert 'BytesWarning' not in result.stdout
    assert result.returncode == 0, result.stdout[-2000:]
