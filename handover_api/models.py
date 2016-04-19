from __future__ import unicode_literals

import uuid
from django.db import models
from django.contrib.auth.models import User

class DukeDSUser(models.Model):
    """
    Represents a DukeDS user. Keeps track of their API key. The API key
    is used when the corresponding user invokes an action that requires
    communication with DukeDS (e.g. mailing a draft or performing handover)

    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    dds_id = models.CharField(max_length=36, null=False, unique=True)
    api_key = models.CharField(max_length=36, null=False, unique=True)

    def __str__(self):
        return 'DukeDSUser <{}>'.format(self.dds_id)


class State(object):
    """
    States for handover and draft objects
    """
    NEW = 0
    NOTIFIED = 1
    ACCEPTED = 2
    REJECTED = 3
    FAILED = 4
    STATES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    )
    HANDOVER_CHOICES = STATES
    DRAFT_CHOICES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (FAILED, 'Failed'),
    )


class Handover(models.Model):
    """
    Represents a handover of a project from one user to another
    Handovers keep track of the project, sender, and recipient by their DukeDS IDs.
    When a handover is notified, an email is sent to the recipient with an acceptance
    link. The recipient can accept or reject the handover. On acceptance, the DukeDS
    API is contacted to transfer ownership from the sender to the receiver.
    The state indicates the current progress of the handover, and are enumerated
    above.
    """
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.HANDOVER_CHOICES, default=State.NEW, null=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    reject_reason = models.TextField(null=True, blank=True)

    def is_new(self):
        return self.state == State.NEW

    def mark_notified(self, save=True):
        self.state = State.NOTIFIED
        if save: self.save()

    def mark_accepted(self, save=True):
        self.state = State.ACCEPTED
        if save: self.save()

    def mark_rejected(self, reason, save=True):
        self.state = State.REJECTED
        self.reject_reason = reason
        if save: self.save()

    def __str__(self):
        return 'Handover <Project: {}, From: {}, To: {}, State: {}>'.format(
            self.project_id, self.from_user_id, self.to_user_id, State.HANDOVER_CHOICES[self.state][1]
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')

class Draft(models.Model):
    """
    Represents a non-destructive preview of a project from one user to another.
    Drafts keep track of the project, sender, and recipient by their DukeDS IDs.
    Drafts can be sent, which looks up user/project details and sends an email to the
    recipient with a preview link. States are enumerated above.

    """
    project_id = models.CharField(max_length=36, null=False)
    from_user_id = models.CharField(max_length=36, null=False)
    to_user_id = models.CharField(max_length=36, null=False)
    state = models.IntegerField(choices=State.DRAFT_CHOICES, default=State.NEW, null=False)

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
