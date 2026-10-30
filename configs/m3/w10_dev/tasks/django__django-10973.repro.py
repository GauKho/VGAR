"""Issue: the postgres client should run psql with subprocess.run and pass the password through PGPASSWORD."""
from unittest import mock

from django.db.backends.postgresql.client import DatabaseClient
from django.test import SimpleTestCase


class Repro(SimpleTestCase):
    def test_runshell_uses_subprocess_run_with_pgpassword(self):
        params = {'database': 'dbname', 'user': 'someuser', 'password': 'somepassword',
                  'host': 'somehost', 'port': '444'}
        # psql is not installed in the testbed; the old call path is stubbed so it fails on the assertion, not on ENOENT.
        with mock.patch('subprocess.run') as run, mock.patch('subprocess.check_call'):
            DatabaseClient.runshell_db(params)
        self.assertTrue(run.called)
        self.assertEqual(run.call_args[1]['env']['PGPASSWORD'], 'somepassword')
