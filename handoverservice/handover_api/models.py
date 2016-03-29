from __future__ import unicode_literals

from django.db import models

class User(models.Model):
    dds_id = models.CharField(max_length=36, null=False, unique=True)
    api_key = models.CharField(max_length=36, null=False)


class State(object):
    INITIATED = 0
    NOTIFIED = 1
    ACCEPTED = 2
    REJECTED = 3
    HANDOVER_CHOICES = (
        (INITIATED, 'Initiated'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    )
    DRAFT_CHOICES = (
        (NOTIFIED, 'Notified'),
    )


class Handover(models.Model):
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.HANDOVER_CHOICES, default=State.INITIATED, null=False)

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')

class Draft(models.Model):
    STATE_CHOICES = ((1,'Notified',),)
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.DRAFT_CHOICES, default=State.NOTIFIED, null=False)

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')
