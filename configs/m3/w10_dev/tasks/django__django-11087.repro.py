"""Issue: QuerySet.delete() fetches every column of the related objects it collects (e.g. a text field with
undecodable data); it should only select the fields deletion needs."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import FailureLine, Job


class Repro(TestCase):
    def test_delete_does_not_fetch_unneeded_related_fields(self):
        job = Job.objects.create(name='j')
        FailureLine.objects.create(job=job, line='text')
        with CaptureQueriesContext(connection) as context:
            Job.objects.filter(pk=job.pk).delete()
        column = connection.ops.quote_name('line')
        selects = [q['sql'] for q in context.captured_queries if q['sql'].startswith('SELECT')]
        self.assertFalse([sql for sql in selects if column in sql], selects)
