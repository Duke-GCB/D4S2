from __future__ import unicode_literals

import uuid
from django.db import models
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError
from django.contrib.auth.models import User, Group
from simple_history.models import HistoricalRecords

DEFAULT_EMAIL_TEMPLATE_SET_NAME = 'default'


class DukeDSUser(models.Model):
    """
    Represents a DukeDS user.
    is used when the corresponding user invokes an action that requires
    communication with DukeDS (e.g. sharing a project or performing delivery)

    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    dds_id = models.CharField(max_length=36, null=False, unique=True)

    def __str__(self):
        return "{} - {}".format(self.user.username, self.dds_id)


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
    project_id = models.CharField(max_length=255, help_text='DukeDS uuid project to deliver')
    from_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user sending delivery')
    to_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user receiving delivery')
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
            self.project_id, State.DELIVERY_CHOICES[self.state][1], self.performed_by
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')


class DeliveryShareUser(models.Model):
    dds_id = models.CharField(max_length=36)
    delivery = models.ForeignKey(Delivery, related_name='share_users')

    class Meta:
        unique_together = ('dds_id', 'delivery')


class Share(models.Model):
    """
    Represents a non-destructive preview of a project from one user to another.
    Share keep track of the project, sender, and recipient by their DukeDS IDs.
    Shares can be sent, which looks up user/project details and sends an email to the
    recipient with a preview link. States are enumerated above.

    """
    history = HistoricalRecords()
    project_id = models.CharField(max_length=255, help_text='DukeDS uuid project to share with')
    from_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user sharing the project')
    to_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user having project shared with them')
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
            self.project_id, State.DELIVERY_CHOICES[self.state][1]
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id', 'role')


class EmailTemplateException(BaseException):
    pass


class EmailTemplateSet(models.Model):
    """
    Set of email templates with unique template types.
    """
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)

    def __str__(self):
        return self.name


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
    template_set = models.ForeignKey(EmailTemplateSet)
    owner = models.ForeignKey(User)
    template_type = models.ForeignKey(EmailTemplateType)
    body = models.TextField(null=False, blank=False)
    subject = models.TextField(null=False, blank=False)

    def __str__(self):
        return 'Email Template in set <{}>, type <{}>: {}'.format(
            self.template_set,
            self.template_type,
            self.subject,
        )

    class Meta:
        unique_together = (
            ('template_set', 'template_type'),
        )

    @classmethod
    def for_operation(cls, operation, template_type_name):
        """
        Lookup the EmailTemplate for the provided operation and template_type_name.
        Returns per user EmailTemplateSet specified in the database or falls back to DEFAULT_EMAIL_TEMPLATE_SET_NAME.
        :param operation: Delivery/Share: object with from_user_id field
        :param template_type_name: str: name specifying what specific operation within a template set to use
        :return: EmailTemplate
        """
        try:
            user_email_template_set = EmailTemplate.get_user_email_template_set(operation.from_user_id)
            if user_email_template_set:
                email_template_set = user_email_template_set.email_template_set
            else:
                email_template_set = EmailTemplateSet.objects.get(name=DEFAULT_EMAIL_TEMPLATE_SET_NAME)
            return EmailTemplate.objects.get(
                template_set=email_template_set,
                template_type__name=template_type_name)
        except (EmailTemplate.DoesNotExist, EmailTemplateSet.DoesNotExist):
            raise EmailTemplateException(
                "Setup Error: Unable to find email template for type {}".format(template_type_name))

    @staticmethod
    def get_user_email_template_set(from_user_id):
        """
        Lookup the UserEmailTemplateSet based on from_user_id or None if not found.
        :param from_user_id: str: DukeDS uuid of the from user
        :return: UserEmailTemplateSet or None
        """
        try:
            dds_user = DukeDSUser.objects.get(dds_id=from_user_id)
            user = dds_user.user
            if user:
                return UserEmailTemplateSet.objects.get(user=user)
            return None
        except (DukeDSUser.DoesNotExist, UserEmailTemplateSet):
            return None

    @classmethod
    def for_share(cls, share):
        type_name = 'share_{}'.format(share.role)
        return cls.for_operation(share, type_name)


class UserEmailTemplateSet(models.Model):
    """
    Specifies an email template to use for a user
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False)
    email_template_set = models.ForeignKey(EmailTemplateSet, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return 'User Email Template Set user <{}>, set: <{}>'.format(self.user.username, self.email_template_set.name)
