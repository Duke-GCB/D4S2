from __future__ import unicode_literals

import uuid
from django.db import models
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.contrib.auth.models import User, Group
from simple_history.models import HistoricalRecords


class DukeDSUser(models.Model):
    """
    Represents a DukeDS user.
    is used when the corresponding user invokes an action that requires
    communication with DukeDS (e.g. sharing a project or performing delivery)

    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    dds_id = models.CharField(max_length=36, null=False, unique=True)
    full_name = models.TextField(null=True)
    email = models.EmailField(null=True)

    objects = models.Manager()

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

class DDSProjectTransferDetails(object):
    class Fields(object):
        """
        Fields of interest in project_transfer paylods
        """
        STATUS = 'status'
        STATUS_COMMENT = 'status_comment'
        FROM_USER = 'from_user'
        TO_USERS = 'to_users'
        PROJECT = 'project'

    class Status(object):
        """
        States for Duke Data Service project_transfers
        """
        PENDING = 'pending'
        REJECTED = 'rejected'
        ACCEPTED = 'accepted'
        CANCELED = 'canceled'



class State(object):
    """
    States for delivery and share objects
    """
    NEW = 0
    NOTIFIED = 1
    ACCEPTED = 2
    DECLINED = 3
    FAILED = 4
    STATES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
    )
    DELIVERY_CHOICES = STATES
    SHARE_CHOICES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (FAILED, 'Failed'),
    )


class TransferStatusLookup(object):
    TransferStatusMap = {
        DDSProjectTransferDetails.Status.PENDING: State.NEW,
        DDSProjectTransferDetails.Status.ACCEPTED: State.ACCEPTED,
        DDSProjectTransferDetails.Status.REJECTED: State.DECLINED,
        DDSProjectTransferDetails.Status.CANCELED: State.FAILED,
    }

    @classmethod
    def get(cls, status):
        return cls.TransferStatusMap.get(status)


class ShareRole(object):
    """
    Known roles for sharing. This is not enforced as a validator or choices since these roles
    are defined by Duke Data Service. Instead they are offered as constants for convenience.
    """
    DOWNLOAD = 'file_downloader'
    VIEW = 'project_viewer'
    EDIT = 'file_editor'
    UPLOAD = 'file_uploader'
    ADMIN = 'project_admin'
    ROLES = (DOWNLOAD, VIEW, EDIT, UPLOAD, ADMIN)
    DEFAULT = DOWNLOAD


class Delivery(models.Model):
    """
    Represents a delivery of a project from one user to another
    Deliveries keep track of the project, sender, and recipient by their DukeDS IDs.
    When a delivery is notified, an email is sent to the recipient with an acceptance
    link. The recipient can accept or decline the delivery. On acceptance, the DukeDS
    API is contacted to transfer ownership from the sender to the receiver.
    The state indicates the current progress of the delivery, and are enumerated
    above.
    """
    history = HistoricalRecords()
    project = models.ForeignKey(DukeDSProject)
    from_user = models.ForeignKey(DukeDSUser, related_name='deliveries_from')
    to_users = models.ManyToManyField(DukeDSUser, related_name='deliveries_to_users')
    state = models.IntegerField(choices=State.DELIVERY_CHOICES, default=State.NEW, null=False)
    transfer_id = models.CharField(max_length=36, null=False, unique=True)
    decline_reason = models.TextField(null=False, blank=True)
    performed_by = models.TextField(null=False, blank=True) # logged-in user that accepted or declined the delivery
    delivery_email_text = models.TextField(null=False, blank=True)
    completion_email_text = models.TextField(null=False, blank=True)
    user_message = models.TextField(null=True, blank=True,
                                    help_text='Custom message to include about this item when sending notifications')

    def is_new(self):
        return self.state == State.NEW

    def is_complete(self):
        return self.state == State.ACCEPTED or self.state == State.DECLINED or self.state == State.FAILED

    def mark_notified(self, email_text, save=True):
        self.state = State.NOTIFIED
        self.delivery_email_text = email_text
        if save: self.save()

    def mark_accepted(self, performed_by, accept_email_text, save=True):
        self.state = State.ACCEPTED
        self.performed_by = performed_by
        self.completion_email_text = accept_email_text
        if save: self.save()

    def mark_declined(self, performed_by, reason, decline_email_text, save=True):
        self.state = State.DECLINED
        self.performed_by = performed_by
        self.decline_reason = reason
        self.completion_email_text = decline_email_text
        if save: self.save()

    def update_state_from_project_transfer(self, project_transfer={}):
        """
        Updates a Delivery object with details from a DukeDS project_transfer
        :param project_transfer: a dictionary containing details of a project_transfer, e.g. {'id': 'abc', 'status': 'rejected'...}
        :return: None
        """
        # sync the project
        remote_status = project_transfer.get(DDSProjectTransferDetails.Fields.STATUS)
        local_state = TransferStatusLookup.get(remote_status)
        if not self.state == local_state:
            # State has changed
            self.state = local_state
            if local_state == State.DECLINED:
                self.decline_reason = project_transfer.get(DDSProjectTransferDetails.Fields.STATUS_COMMENT)
            self.save()

    def __str__(self):
        return 'Delivery Project: {} State: {} Performed by: {}'.format(
            self.project, State.DELIVERY_CHOICES[self.state][1], self.performed_by
        )


class Share(models.Model):
    """
    Represents a non-destructive preview of a project from one user to another.
    Share keep track of the project, sender, and recipient by their DukeDS IDs.
    Shares can be sent, which looks up user/project details and sends an email to the
    recipient with a preview link. States are enumerated above.

    """
    history = HistoricalRecords()
    project = models.ForeignKey(DukeDSProject)
    from_user = models.ForeignKey(DukeDSUser, related_name='shares_from')
    to_users = models.ManyToManyField(DukeDSUser, related_name='shares_to_users')
    state = models.IntegerField(choices=State.SHARE_CHOICES, default=State.NEW, null=False)
    email_text = models.TextField(null=False, blank=True)
    role = models.TextField(null=False, blank=False, default=ShareRole.DEFAULT)
    user_message = models.TextField(null=True, blank=True,
                                    help_text='Custom message to include about this item when sending notifications')

    def is_notified(self):
        return self.state == State.NOTIFIED

    def mark_notified(self, email_text, save=True):
        self.state = State.NOTIFIED
        self.email_text = email_text
        if save: self.save()

    def __str__(self):
        return 'Share of Project: {} State: {}'.format(
            self.project, State.DELIVERY_CHOICES[self.state][1]
        )


class EmailTemplateException(BaseException):
    pass

class EmailTemplateType(models.Model):
    """
    Type of email template, e.g. share_project_viewer, delivery, final_notification
    """
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)

    def __str__(self):
        return self.name

    @classmethod
    def from_share_role(cls, role):
        return cls.objects.get(name='share_{}'.format(role))


class EmailTemplate(models.Model):
    """
    Represents a base email message that can be sent
    """
    history = HistoricalRecords()
    group = models.ForeignKey(Group)
    owner = models.ForeignKey(User)
    template_type = models.ForeignKey(EmailTemplateType)
    body = models.TextField(null=False, blank=False)
    subject = models.TextField(null=False, blank=False)

    def __str__(self):
        return 'Email Template in group <{}>, type <{}>: {}'.format(
            self.template_type,
            self.group,
            self.subject,
        )
    class Meta:
        unique_together = (
            ('group','template_type'),
        )

    @classmethod
    def for_operation(cls, operation, template_type_name):
        user = operation.from_user.user
        if user is None:
            raise EmailTemplateException('User object not found in {}'.format(operation))
        matches = cls.objects.filter(group__in=user.groups.all(), template_type__name=template_type_name)
        if len(matches) == 0:
            return None
        elif len(matches) > 1:
            raise EmailTemplateException('Multiple email templates found for type {}'.format(template_type_name))
        else:
            return matches.first()

    @classmethod
    def for_share(cls, share):
        type_name = 'share_{}'.format(share.role)
        return cls.for_operation(share, type_name)
