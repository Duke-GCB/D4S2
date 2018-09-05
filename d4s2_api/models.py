from __future__ import unicode_literals

import uuid
from django.db import models
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError
from django.contrib.auth.models import User, Group
from django.contrib.postgres.fields import JSONField
from simple_history.models import HistoricalRecords

DEFAULT_EMAIL_TEMPLATE_SET_NAME = 'default'


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
    TRANSFERRING = 5
    RESCINDED = 6
    STATES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
        (FAILED, 'Failed'),
        (TRANSFERRING, 'Transferring'),
        (RESCINDED, 'Rescinded')
    )
    DELIVERY_CHOICES = STATES
    SHARE_CHOICES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (FAILED, 'Failed'),
    )


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


class DeliveryBase(models.Model):
    state = models.IntegerField(choices=State.DELIVERY_CHOICES, default=State.NEW, null=False)
    decline_reason = models.TextField(null=False, blank=True)
    performed_by = models.TextField(null=False, blank=True) # logged-in user that accepted or declined the delivery
    delivery_email_text = models.TextField(null=False, blank=True)
    sender_completion_email_text = models.TextField(blank=True)
    recipient_completion_email_text = models.TextField(blank=True)
    user_message = models.TextField(null=True, blank=True,
                                    help_text='Custom message to include about this item when sending notifications')

    def is_new(self):
        return self.state == State.NEW

    def is_complete(self):
        return self.state == State.ACCEPTED or self.state == State.DECLINED or self.state == State.FAILED or \
               self.state == State.RESCINDED

    def mark_notified(self, email_text, save=True):
        self.state = State.NOTIFIED
        self.delivery_email_text = email_text
        if save: self.save()

    def mark_accepted(self, performed_by, sender_completion_email_text,
                      recipient_completion_email_text='', save=True):
        self.state = State.ACCEPTED
        self.performed_by = performed_by
        self.sender_completion_email_text = sender_completion_email_text
        self.recipient_completion_email_text = recipient_completion_email_text
        if save: self.save()

    def mark_declined(self, performed_by, reason, sender_decline_email_text, save=True):
        self.state = State.DECLINED
        self.performed_by = performed_by
        self.decline_reason = reason
        self.sender_completion_email_text = sender_decline_email_text
        if save: self.save()

    def mark_transferring(self, save=True):
        self.state = State.TRANSFERRING
        if save: self.save()

    def mark_failed(self, save=True):
        self.state = State.FAILED
        if save: self.save()

    def mark_rescinded(self, save=True):
        self.state = State.RESCINDED
        if save: self.save()

    class Meta:
        abstract = True


class DDSDelivery(DeliveryBase):
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
    transfer_id = models.CharField(max_length=36, null=False, unique=True)

    def __str__(self):
        return 'Delivery Project: {} State: {} Performed by: {}'.format(
            self.project_id, State.DELIVERY_CHOICES[self.state][1], self.performed_by
        )

    class Meta:
        unique_together = ('project_id', 'from_user_id', 'to_user_id')


class DDSDeliveryError(models.Model):
    message = models.TextField()
    delivery = models.ForeignKey(DDSDelivery, on_delete=models.CASCADE, related_name='errors')
    created = models.DateTimeField(auto_now_add=True)


class DDSDeliveryShareUser(models.Model):
    dds_id = models.CharField(max_length=36)
    delivery = models.ForeignKey(DDSDelivery, related_name='share_users')

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
    def for_user(cls, user, template_type_name):
        """
        Lookup the EmailTemplate for the provided operation and template_type_name.
        Returns per user EmailTemplateSet specified in the database or falls back to DEFAULT_EMAIL_TEMPLATE_SET_NAME.
        :param user: User: django user to lookup a template for
        :param template_type_name: str: name specifying what specific operation within a template set to use
        :return: EmailTemplate
        """
        try:

            user_email_template_set = EmailTemplate.get_user_email_template_set(user)
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
    def get_user_email_template_set(user):
        """
        Lookup the UserEmailTemplateSet based on from_user_id or None if not found.
        :param user: django user
        :return: UserEmailTemplateSet or None
        """
        try:
            return UserEmailTemplateSet.objects.get(user=user)
        except (UserEmailTemplateSet.DoesNotExist):
            return None

    @classmethod
    def for_share(cls, share, user):
        type_name = 'share_{}'.format(share.role)
        return cls.for_user(user, type_name)


class UserEmailTemplateSet(models.Model):
    """
    Specifies an email template to use for a user
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=False)
    email_template_set = models.ForeignKey(EmailTemplateSet, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return 'User Email Template Set user <{}>, set: <{}>'.format(self.user.username, self.email_template_set.name)


class S3EndpointManager(models.Manager):
    def get_by_natural_key(self, url):
        return self.get(url=url)


class S3Endpoint(models.Model):
    """
    Defines S3 service provider
    """
    objects = S3EndpointManager()
    url = models.CharField(max_length=255, help_text='URL of S3 service', unique=True)
    name = models.CharField(max_length=255, help_text='Unique name of the s3 service', unique=True)

    def __str__(self):
        return 'S3 Endpoint url: {}'.format(self.url)


class S3UserTypes(object):
    NORMAL = 0
    AGENT = 1
    CHOICES = (
        (NORMAL, 'Normal'),
        (AGENT, 'Agent'),
    )


class S3User(models.Model):
    endpoint = models.ForeignKey(S3Endpoint)
    s3_id = models.CharField(max_length=255, help_text='S3 user ID (aws_access_key_id)')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.IntegerField(choices=S3UserTypes.CHOICES, default=S3UserTypes.NORMAL)

    def get_type_label(self):
        type_choice = S3UserTypes.CHOICES[self.type]
        if type_choice:
            return type_choice[1]
        return ''

    def __str__(self):
        return 'S3User s3_id: {} user: {} type: {}'.format(self.s3_id, self.user, self.get_type_label())

    class Meta:
        # TODO: put below in once we have an actual separate agent credential
        # unique_together = (('endpoint', 'user'), ('endpoint', 's3_id'))
        unique_together = ('endpoint', 'user')


class S3UserCredential(models.Model):
    s3_user = models.OneToOneField(S3User, related_name='credential')
    aws_secret_access_key = models.CharField(max_length=255, help_text='S3 user ID (aws_access_key_id)')

    def __str__(self):
        return 'S3UserCredential user: {}'.format(self.s3_user)


class S3Bucket(models.Model):
    """
    Represents a bucket that exists in an s3 service.
    This is duplicated to allow us to show bucket names to users receiving deliveries.
    """
    name = models.CharField(max_length=255, help_text='Name of S3 bucket')
    owner = models.ForeignKey(S3User, related_name='owned_buckets')
    endpoint = models.ForeignKey(S3Endpoint, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return 'S3 Bucket: {} Endpoint: {} '.format(self.name, self.endpoint)

    class Meta:
        unique_together = ('endpoint', 'name')


class S3ObjectManifest(models.Model):
    content = JSONField(help_text='JSON array of object metadata from bucket at time of sending bucket')


class S3Delivery(DeliveryBase):
    """
    Represents a delivery of a s3 bucket from one user to another.
    When a delivery is notified, an email is sent to the recipient with an acceptance
    link. The recipient can accept or decline the delivery. On acceptance, the bucket is copied
    to a new bucket owned by the recipient.
    """
    history = HistoricalRecords()
    bucket = models.ForeignKey(S3Bucket, related_name='deliveries')
    from_user = models.ForeignKey(S3User, related_name='sent_deliveries')
    to_user = models.ForeignKey(S3User, related_name='received_deliveries')
    transfer_id = models.UUIDField(default=uuid.uuid4)
    manifest = models.OneToOneField(S3ObjectManifest, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return 'S3 Delivery bucket: {} State: {} Performed by: {}'.format(
            self.bucket, State.DELIVERY_CHOICES[self.state][1], self.performed_by
        )

    class Meta:
        unique_together = ('bucket', 'from_user', 'to_user')


class S3DeliveryError(models.Model):
    message = models.TextField()
    delivery = models.ForeignKey(S3Delivery, on_delete=models.CASCADE, related_name='errors')
    created = models.DateTimeField(auto_now_add=True)
