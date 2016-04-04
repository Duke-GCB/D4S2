from __future__ import unicode_literals

from django.db import models

class User(models.Model):
    dds_id = models.CharField(max_length=36, null=False, unique=True)
    api_key = models.CharField(max_length=36, null=False)

    def __str__(self):
        return 'User <{}>'.format(self.dds_id)


class State(object):
    INITIATED = 0
    NOTIFIED = 1
    ACCEPTED = 2
    REJECTED = 3
    FAILED = 4
    STATES = (
        (INITIATED, 'Initiated'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    )
    HANDOVER_CHOICES = STATES
    DRAFT_CHOICES = (
        (INITIATED, 'Initiated'),
        (NOTIFIED, 'Notified'),
        (FAILED, 'Failed'),
    )


class Handover(models.Model):
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.HANDOVER_CHOICES, default=State.INITIATED, null=False)

    def __str__(self):
        return 'Handover <Project: {}, From: {}, To: {}, State: {}>'.format(
            self.project_id, self.from_user_id, self.to_user_id, State.HANDOVER_CHOICES[self.state][1]
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')

class Draft(models.Model):
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.DRAFT_CHOICES, default=State.INITIATED, null=False)

    def is_notified(self):
        return self.state == State.NOTIFIED

    def mark_notified(self, save=True):
        self.state = State.NOTIFIED
        if save: self.save()

    def __str__(self):
        return 'Draft <Project: {}, From: {}, To: {}, State: {}>'.format(
            self.project_id, self.from_user_id, self.to_user_id, State.HANDOVER_CHOICES[self.state][1]
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')
