"""Issue: the default FILE_UPLOAD_PERMISSIONS should be 0o644 so uploaded files get consistent permissions."""
from django.conf import global_settings
from django.test import SimpleTestCase


class Repro(SimpleTestCase):
    def test_default_file_upload_permissions(self):
        self.assertEqual(global_settings.FILE_UPLOAD_PERMISSIONS, 0o644)
