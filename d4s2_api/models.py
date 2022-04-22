from __future__ import unicode_literals

import uuid
import os.path
from django.db import models
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError
from django.contrib.auth.models import User, Group
from django.contrib.postgres.fields import JSONField, ArrayField
from simple_history.models import HistoricalRecords
from gcb_web_auth.utils import get_default_oauth_service, current_user_details, OAuthConfigurationException
from gcb_web_auth.models import DDSUserCredential, GroupManagerConnection
from gcb_web_auth.groupmanager import get_users_group_names


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
    CANCELED = 6
    STATES = (
        (NEW, 'New'),
        (NOTIFIED, 'Notified'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
        (FAILED, 'Failed'),
        (TRANSFERRING, 'Transferring'),
        (CANCELED, 'Canceled')
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

    @staticmethod
    def email_template_name(role):
        return 'share_{}'.format(role)


class StorageTypes(object):
    """
    States for delivery and share objects
    """
    DDS = 'dds'
    AZURE = 'azure'
    S3 = 's3'
    CHOICES = (
        (DDS, 'Duke Data Service'),
        (AZURE, 'Azure Blob Storage'),
        (S3, 'S3'),
    )


class EmailTemplateSet(models.Model):
    """
    Set of email templates with unique template types.
    """
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    cc_address = models.EmailField(blank=True, help_text='Optional address to CC when using this template set')
    reply_address = models.EmailField(blank=True, help_text='Optional address to set as reply-to when using this template set (replacing the sending user\'s email address')
    group_name = models.CharField(max_length=64, null=False, blank=True,
                                  help_text='group manager group assigned to this set')
    storage = models.CharField(max_length=64, choices=StorageTypes.CHOICES, default=StorageTypes.DDS)

    def __str__(self):
        return self.name

    def get_storage_name(self):
        for k,v in StorageTypes.CHOICES:
            if k == self.storage:
                return v
        return "Unknown {}".format(self.storage)

    def template_for_name(self, name):
        try:
            return EmailTemplate.objects.get(template_set=self, template_type__name=name)
        except EmailTemplate.DoesNotExist:
            raise EmailTemplateException(
                "Setup Error: Unable to find email template for type {}".format(name))

    @staticmethod
    def get_group_names_for_user(user):
        try:
            user_details = current_user_details(get_default_oauth_service(), user)
            duke_unique_id = user_details['dukeUniqueID']
            group_manager_connection = GroupManagerConnection.objects.first()
            if group_manager_connection and duke_unique_id:
                group_manager_groups = get_users_group_names(group_manager_connection, duke_unique_id)
                return [group_name for group_name in group_manager_groups if group_name]
            else:
                return []
        except OAuthConfigurationException:
            return []

    @staticmethod
    def get_for_user(user, storage=None):
        """
        Include a users default template set and those for the current user's groups.
        """
        user_group_names = EmailTemplateSet.get_group_names_for_user(user)
        query_set = EmailTemplateSet.objects
        if storage:
            query_set = query_set.filter(storage=storage)
        return query_set.filter(
            Q(useremailtemplateset__user=user) |
            Q(group_name__in=user_group_names)
        )


class DeliveryBase(models.Model):
    state = models.IntegerField(choices=State.DELIVERY_CHOICES, default=State.NEW, null=False)
    decline_reason = models.TextField(null=False, blank=True)
    performed_by = models.TextField(null=False, blank=True) # logged-in user that accepted or declined the delivery
    delivery_email_text = models.TextField(null=False, blank=True)
    sender_completion_email_text = models.TextField(blank=True)
    recipient_completion_email_text = models.TextField(blank=True)
    user_message = models.TextField(null=True, blank=True,
                                    help_text='Custom message to include about this item when sending notifications')
    email_template_set = models.ForeignKey(EmailTemplateSet, null=True, on_delete=models.CASCADE,
                                           help_text='Email template set to be used with this delivery')

    def is_new(self):
        return self.state == State.NEW

    def is_complete(self):
        return self.state == State.ACCEPTED or self.state == State.DECLINED or self.state == State.FAILED or \
               self.state == State.CANCELED

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

    def mark_canceled(self, save=True):
        self.state = State.CANCELED
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
    project_name = models.TextField(help_text='Copy of the project name from when delivery is accepted.', default='',
                                    blank=True)
    from_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user sending delivery')
    to_user_id = models.CharField(max_length=255, help_text='DukeDS uuid user receiving delivery')
    transfer_id = models.CharField(max_length=36, null=False, unique=True)

    def __str__(self):
        return 'Delivery Project: {} State: {} Performed by: {}'.format(
            self.project_id, State.DELIVERY_CHOICES[self.state][1], self.performed_by
        )


class DDSDeliveryError(models.Model):
    message = models.TextField()
    delivery = models.ForeignKey(DDSDelivery, on_delete=models.CASCADE, related_name='errors')
    created = models.DateTimeField(auto_now_add=True)


class DDSDeliveryShareUser(models.Model):
    dds_id = models.CharField(max_length=36)
    delivery = models.ForeignKey(DDSDelivery, related_name='share_users', on_delete=models.CASCADE)

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
    email_template_set = models.ForeignKey(EmailTemplateSet, null=True, on_delete=models.CASCADE,
                                           help_text='Email template set to be used with this share')

    def email_template_name(self):
        return ShareRole.email_template_name(self.role)

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


class EmailTemplateType(models.Model):
    """
    Type of email template, e.g. share_project_viewer, delivery, final_notification
    """
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    help_text = models.TextField(null=False, blank=True)
    sequence = models.IntegerField(null=True, help_text='determines order')

    def __str__(self):
        return self.name


class EmailTemplate(models.Model):
    """
    Represents a base email message that can be sent
    """
    history = HistoricalRecords()
    template_set = models.ForeignKey(EmailTemplateSet, on_delete=models.CASCADE, related_name='email_templates')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    template_type = models.ForeignKey(EmailTemplateType, on_delete=models.CASCADE)
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

    @staticmethod
    def get_for_user(user):
        """
        Include a users default template set templates and those for the current user's groups.
        """
        user_group_names = EmailTemplateSet.get_group_names_for_user(user)
        return EmailTemplate.objects.filter(
            Q(template_set__useremailtemplateset__user=user) |
            Q(template_set__group_name__in=user_group_names)
        )


class UserEmailTemplateSet(models.Model):
    """
    Specifies an email template to use for a user
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    email_template_set = models.ForeignKey(EmailTemplateSet, on_delete=models.CASCADE, null=False)
    storage = models.CharField(max_length=64, choices=StorageTypes.CHOICES, default=StorageTypes.DDS)

    def __str__(self):
        return 'User Email Template Set user <{}>, set: <{}>'.format(self.user.username, self.email_template_set.name)

    @staticmethod
    def user_is_setup(user, storage=StorageTypes.DDS):
        """
        Returns True if the user has their email templates setup
        :param user: User: user to check
        :param storage: str: value from StorageTypes
        :return: boolean: True if user is setup correctly
        """
        return UserEmailTemplateSet.objects.filter(user=user,storage=storage).count() > 0

    class Meta:
        unique_together = ('user', 'storage')


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
    endpoint = models.ForeignKey(S3Endpoint, on_delete=models.CASCADE)
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
    s3_user = models.OneToOneField(S3User, on_delete=models.CASCADE, related_name='credential')
    aws_secret_access_key = models.CharField(max_length=255, help_text='S3 user ID (aws_access_key_id)')

    def __str__(self):
        return 'S3UserCredential user: {}'.format(self.s3_user)


class S3Bucket(models.Model):
    """
    Represents a bucket that exists in an s3 service.
    This is duplicated to allow us to show bucket names to users receiving deliveries.
    """
    name = models.CharField(max_length=255, help_text='Name of S3 bucket')
    owner = models.ForeignKey(S3User, related_name='owned_buckets', on_delete=models.CASCADE)
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
    bucket = models.ForeignKey(S3Bucket, related_name='deliveries', on_delete=models.CASCADE)
    from_user = models.ForeignKey(S3User, related_name='sent_deliveries', on_delete=models.CASCADE)
    to_user = models.ForeignKey(S3User, related_name='received_deliveries', on_delete=models.CASCADE)
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


class AzContainerPath(models.Model):
    """
    Represents a directory(project) within an Azure container/filesystem/bucket
    """
    path = models.CharField(max_length=255, help_text='Path in the Azure container to a directory (project)')
    container_url = models.URLField(help_text='URL to the container where directory (project) resides')

    def make_project_url(self):
        return os.path.join(self.container_url, self.path)

    def __str__(self):
        return 'Azure Project: {} URL: {} '.format(self.path, self.container_url)


class AzObjectManifest(models.Model):
    content = models.TextField(help_text='Signed JSON array of object metadata from project at time of delivery')


class AzTransferStates:
    NEW = 0
    CREATED_MANIFEST = 1
    TRANSFERRED_PROJECT = 2
    ADDED_DOWNLOAD_USERS = 3
    CHANGED_OWNER = 4
    EMAILED_SENDER = 5
    EMAILED_RECIPIENT = 6
    COMPLETE = 7
    CHOICES = (
        (NEW, 'New'),
        (CREATED_MANIFEST, 'Created manifest'),
        (TRANSFERRED_PROJECT, 'Transferred project'),
        (ADDED_DOWNLOAD_USERS, 'Added download users to project'),
        (CHANGED_OWNER, 'Gave recipient owner permissions'),
        (EMAILED_SENDER, 'Emailed Sender'),
        (EMAILED_RECIPIENT, 'Emailed Recipient'),
        (COMPLETE, 'Delivery Complete'),
    )


class AzDelivery(DeliveryBase):
    """
    Represents a delivery of a Azure container/bucket from one user to another.
    When a delivery is notified, an email is sent to the recipient with an acceptance
    link. The recipient can accept or decline the delivery. On acceptance, the bucket is moved/copied
    to the destination.
    """
    history = HistoricalRecords()
    source_project = models.ForeignKey(AzContainerPath, related_name='from_project', on_delete=models.CASCADE)
    from_netid = models.CharField(max_length=255, help_text='NetID of the sending user.')
    destination_project = models.ForeignKey(AzContainerPath, related_name='to_project', null=True, blank=True,
                                            on_delete=models.CASCADE)
    to_netid = models.CharField(max_length=255, help_text='NetID of the recipient user.')
    manifest = models.OneToOneField(AzObjectManifest, on_delete=models.CASCADE, null=True, blank=True)
    share_user_ids = ArrayField(models.CharField(max_length=255), blank=True, default=[])
    transfer_state = models.IntegerField(choices=AzTransferStates.CHOICES, default=AzTransferStates.NEW,
                                         help_text='State within transfer')


    def get_simple_project_name(self):
        return os.path.basename(self.source_project.path)

    def make_project_url(self):
        return self.get_current_project().make_project_url()

    def get_current_project(self):
        if self.state == State.ACCEPTED:
            return self.destination_project
        else:
            return self.source_project

    @property
    def transfer_id(self):
        return self.id

    def get_status(self):
        return State.DELIVERY_CHOICES[self.state][1]

    def __str__(self):
        return 'Azure Delivery: {} - {}  State: {}  To: {}  Performed by: {}'.format(
            self.id, self.source_project.path, State.DELIVERY_CHOICES[self.state][1], self.to_netid, self.performed_by
        )

    @staticmethod
    def get_incomplete_delivery(from_netid, source_container_url, source_path):
        """
        Return a incomplete delivery for the specified keys or None if not found.
        There should only be at most one incomplete delivery at a time for a set of keys.
        """
        deliveries = AzDelivery.objects.filter(
            from_netid=from_netid,
            source_project__container_url=source_container_url,
            source_project__path=source_path
        )
        for delivery in deliveries:
            if not delivery.is_complete():
                return delivery
        return None


class AzDeliveryError(models.Model):
    message = models.TextField()
    delivery = models.ForeignKey(AzDelivery, on_delete=models.CASCADE, related_name='errors')
    created = models.DateTimeField(auto_now_add=True)


class AzStorageConfig(models.Model):
    name = models.CharField(max_length=255, help_text='User facing name for these storage config settings.')
    subscription_id = models.CharField(max_length=255,
                                       help_text='Azure subscription id that contains the resource group.')
    resource_group = models.CharField(max_length=255,
                                      help_text='Azure Resource Group containing the storage account.')
    storage_account = models.CharField(max_length=255,
                                       help_text='Azure storage account containing the container (bucket).')
    container_name = models.CharField(max_length=255,
                                      help_text='Azure container (bucket) where files will be stored.')
    storage_account_key = models.CharField(max_length=255, help_text='Azure storage account key.',
                                           blank=True)
