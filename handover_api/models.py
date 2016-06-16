from __future__ import unicode_literals

import uuid
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

class APIUserManager(models.Manager):
    """
    Manager to return API users - those with API keys
    """
    def get_queryset(self):
        return super(APIUserManager, self).get_queryset().exclude(api_key__isnull=True)


class DukeDSUser(models.Model):
    """
    Represents a DukeDS user. Keeps track of their API key. The API key
    is used when the corresponding user invokes an action that requires
    communication with DukeDS (e.g. mailing a draft or performing handover)

    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    dds_id = models.CharField(max_length=36, null=False, unique=True)
    api_key = models.CharField(max_length=36, null=True, unique=True)
    full_name = models.TextField(null=True)
    email = models.EmailField(null=True)

    objects = models.Manager()
    api_users = APIUserManager()

    def populated(self):
        if self.full_name and self.email:
            return True
        else:
            return False

    def __str__(self):
        return "{} - {} - {}".format(self.dds_id, self.email, self.full_name,)


class DukeDSProject(models.Model):
    project_id = models.CharField(max_length=36, null=False, unique=True)
    name = models.TextField(null=True)

    def populated(self):
        # Only field to populate is name
        return bool(self.name)

    def __str__(self):
        return "{} - {}".format(self.project_id, self.name,)


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
    history = HistoricalRecords()
    project = models.ForeignKey(DukeDSProject)
    from_user = models.ForeignKey(DukeDSUser, related_name='handovers_from')
    to_user = models.ForeignKey(DukeDSUser, related_name='handovers_to')
    state = models.IntegerField(choices=State.HANDOVER_CHOICES, default=State.NEW, null=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    reject_reason = models.TextField(null=False, blank=True)
    performed_by = models.TextField(null=False, blank=True) # logged-in user that accepted or rejected the handover
    handover_email_text = models.TextField(null=False, blank=True)
    completion_email_text = models.TextField(null=False, blank=True)

    def is_new(self):
        return self.state == State.NEW

    def is_complete(self):
        return self.state == State.ACCEPTED or self.state == State.REJECTED

    def mark_notified(self, email_text, save=True):
        self.state = State.NOTIFIED
        self.handover_email_text = email_text
        if save: self.save()

    def mark_accepted(self, performed_by, accept_email_text, save=True):
        self.state = State.ACCEPTED
        self.performed_by = performed_by
        self.completion_email_text = accept_email_text
        if save: self.save()

    def mark_rejected(self, performed_by, reason, reject_email_text, save=True):
        self.state = State.REJECTED
        self.performed_by = performed_by
        self.reject_reason = reason
        self.completion_email_text = reject_email_text
        if save: self.save()


    def __str__(self):
        return 'Handover Project: {} State: {} Performed by: {}'.format(
            self.project, State.HANDOVER_CHOICES[self.state][1], self.performed_by
        )

    class Meta:
        unique_together = ('project', 'from_user', 'to_user')

class Draft(models.Model):
    """
    Represents a non-destructive preview of a project from one user to another.
    Drafts keep track of the project, sender, and recipient by their DukeDS IDs.
    Drafts can be sent, which looks up user/project details and sends an email to the
    recipient with a preview link. States are enumerated above.

    """
    history = HistoricalRecords()
    project = models.ForeignKey(DukeDSProject)
    from_user = models.ForeignKey(DukeDSUser, related_name='drafts_from')
    to_user = models.ForeignKey(DukeDSUser, related_name='drafts_to')
    state = models.IntegerField(choices=State.DRAFT_CHOICES, default=State.NEW, null=False)
    email_text = models.TextField(null=False, blank=True)

    def is_notified(self):
        return self.state == State.NOTIFIED

    def mark_notified(self, email_text, save=True):
        self.state = State.NOTIFIED
        self.email_text = email_text
        if save: self.save()

    def __str__(self):
        return 'Draft Project: {} State: {}'.format(
            self.project, State.HANDOVER_CHOICES[self.state][1]
        )

    class Meta:
        unique_together = ('project', 'from_user', 'to_user')
