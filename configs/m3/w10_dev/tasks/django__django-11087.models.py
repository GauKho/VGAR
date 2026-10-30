from django.db import models


class Job(models.Model):
    name = models.CharField(max_length=20)


class FailureLine(models.Model):
    job = models.ForeignKey(Job, models.CASCADE)
    line = models.TextField()


class TextLogError(models.Model):
    # A further cascade level: FailureLine rows must be collected (selected), not fast-deleted.
    failure_line = models.ForeignKey(FailureLine, models.CASCADE)
