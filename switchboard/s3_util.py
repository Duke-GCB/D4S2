from d4s2_api.models import S3Delivery, EmailTemplate, S3User, S3UserTypes, S3DeliveryError, State
from d4s2_api.utils import MessageFactory
import boto3
import botocore
from background_task import background


def wrap_s3_exceptions(func):
    """
    Runs func and traps boto exceptions instead raises them as S3Exception
    :param func: function to wrap
    :return: func: wrapped function
    """
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            raise S3Exception(str(e))
    return wrapped


class BackgroundFunctions(object):
    @staticmethod
    @background
    def transfer_delivery(delivery_id):
        """
        Transfer delivery in s3 to recipient. This is the beginning of the transfer process.
        At the end, S3TransferOperation will call the next background function: notify_sender_delivery_accepted.
        :param delivery_id: str: id of delivery to transfer
        """
        try:
            transfer_operation = S3TransferOperation(delivery_id)
            transfer_operation.transfer_delivery_step()
        except Exception as e:
            BackgroundFunctions.record_exception(delivery_id, e)
            raise

    @staticmethod
    @background
    def notify_sender_delivery_accepted(delivery_id, warning_message):
        """
        Send email to the delivery sender that the transfer was accepted. At the end, S3TransferOperation will call the
        next background function: notify_receiver_transfer_complete.
        :param delivery_id: str: id of delivery that is being transferred
        :param warning_message: str: warning message generated during s3 transfer
        """
        try:
            transfer_operation = S3TransferOperation(delivery_id)
            transfer_operation.notify_sender_delivery_accepted_step(warning_message)
        except Exception as e:
            BackgroundFunctions.record_exception(delivery_id, e)
            raise

    @staticmethod
    @background
    def notify_receiver_transfer_complete(delivery_id, warning_message, sender_accepted_email_text):
        """
        Send email to the delivery recipient that the transfer was accepted. At the end, S3TransferOperation will call the
        next background function: mark_delivery_complete.
        :param delivery_id: str: id of delivery that is being transferred
        :param warning_message: str:
        :param sender_accepted_email_text: str:
        :return:
        """
        try:
            transfer_operation = S3TransferOperation(delivery_id)
            transfer_operation.notify_receiver_transfer_complete_step(warning_message, sender_accepted_email_text)
        except Exception as e:
            BackgroundFunctions.record_exception(delivery_id, e)
            raise

    @staticmethod
    @background
    def mark_delivery_complete(delivery_id, sender_accepted_email_text, recipient_accepted_email_text):
        """
        Mark the delivery as accepted. This is the end of the transfer process.
        :param delivery_id: str: id of delivery to mark completed
        :param sender_accepted_email_text: str:
        :param recipient_accepted_email_text: str:
        :return:
        """
        try:
            transfer_operation = S3TransferOperation(delivery_id)
            transfer_operation.mark_delivery_complete_step(sender_accepted_email_text, recipient_accepted_email_text)
        except Exception as e:
            BackgroundFunctions.record_exception(delivery_id, e)
            raise

    @staticmethod
    def record_exception(delivery_id, e):
        error_message = str(e)
        delivery = S3Delivery.objects.get(pk=delivery_id)
        S3DeliveryError.objects.create(delivery=delivery, message=error_message)
        delivery.mark_failed()


class S3DeliveryUtil(object):
    def __init__(self, s3_delivery, user):
        self.s3_delivery = s3_delivery
        self.endpoint = s3_delivery.bucket.endpoint
        self.source_bucket_name = s3_delivery.bucket.name
        self.user = user
        self.s3_agent = S3User.objects.get(type=S3UserTypes.AGENT, endpoint=self.endpoint)
        self.current_s3_user = S3User.objects.get(user=self.user, endpoint=self.endpoint)
        self.destination_bucket_name = 'delivery_{}'.format(self.source_bucket_name)

    @wrap_s3_exceptions
    def give_agent_permissions(self):
        s3 = S3Resource(self.current_s3_user)
        s3.grant_bucket_acl(self.source_bucket_name,
                            grant_full_control_user=self.s3_agent)
        print("Gave agent {} Full Control".format(self.s3_agent.s3_id))

    @wrap_s3_exceptions
    def accept_project_transfer(self):
        self._grant_user_read_permissions(self.s3_delivery.to_user)
        self._copy_files_to_new_destination_bucket()
        self._cleanup_source_bucket()

    def share_with_additional_users(self):
        pass

    def get_warning_message(self):
        return ''

    def _grant_user_read_permissions(self, s3_user):
        """
        Grants s3_user read bucket/object permissions while retaining full control for agent
        using agent's credentials.
        :param s3: boto3 s3 resource as a user with bucket/object acl and listing permissions
        :param s3_user: S3User: user to grant read bucket/object permissions to
        """
        s3 = S3Resource(self.s3_agent)
        s3.grant_bucket_acl(self.source_bucket_name,
                            grant_full_control_user=self.s3_agent,
                            grant_read_user=s3_user)
        s3.grant_objects_acl(self.source_bucket_name,
                             grant_full_control_user=self.s3_agent,
                             grant_read_user=s3_user)
        print("Gave agent {} full and to_user {} read perms".format(self.s3_agent, s3_user))

    def _copy_files_to_new_destination_bucket(self):
        s3 = S3Resource(self.current_s3_user)
        s3.create_bucket(self.destination_bucket_name)
        s3.copy_bucket(self.source_bucket_name, self.destination_bucket_name)

    def _cleanup_source_bucket(self):
        s3 = S3Resource(self.s3_agent)
        s3.delete_bucket(self.source_bucket_name)

    @wrap_s3_exceptions
    def decline_delivery(self, reason):
        print("Declining delivery for reason: {}".format(reason))
        from_s3_user = self.s3_delivery.from_user
        s3 = S3Resource(self.s3_agent)
        s3.grant_bucket_acl(self.source_bucket_name,
                            grant_full_control_user=from_s3_user)
        print("Gave from user {} Full Control".format(from_s3_user.s3_id))


class S3DeliveryDetails(object):
    def __init__(self, s3_delivery, user):
        self.s3_delivery = s3_delivery
        self.user = user

    def get_delivery(self):
        return self.s3_delivery

    def get_from_user(self):
        return self.s3_delivery.from_user.user

    def get_to_user(self):
        return self.s3_delivery.to_user.user

    def get_context(self):
        from_user = self.get_from_user()
        to_user = self.get_to_user()
        bucket_name = self.s3_delivery.bucket.name
        return {
            'service_name': 'S3',
            'transfer_id': str(self.s3_delivery.transfer_id),
            'from_name': '{} {}'.format(from_user.first_name, from_user.last_name),
            'from_email': from_user.email,
            'to_name': '{} {}'.format(to_user.first_name, to_user.last_name),
            'to_email': to_user.email,
            'project_title': bucket_name,
            'project_url': 's3://{}'.format(bucket_name)
        }

    def get_email_context(self, accept_url, process_type, reason, warning_message=''):
        base_context = self.get_context()
        return {
            'project_name': base_context['project_title'],
            'recipient_name': base_context['to_name'],
            'recipient_email': base_context['to_email'],
            'sender_email': base_context['from_email'],
            'sender_name': base_context['from_name'],
            'project_url': base_context['project_url'],
            'accept_url': accept_url,
            'type': process_type,  # accept or decline
            'message': reason,  # decline reason
            'user_message': self.s3_delivery.user_message,
            'warning_message': warning_message,
            'service_name': base_context['service_name'],
        }

    def get_action_template_text(self, action_name):
        email_template = EmailTemplate.for_user(self.user, action_name)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')


class S3Resource(object):
    def __init__(self, s3_user):
        session = boto3.session.Session(aws_access_key_id=s3_user.s3_id,
                                        aws_secret_access_key=s3_user.credential.aws_secret_access_key)
        self.s3 = session.resource('s3', endpoint_url=s3_user.endpoint.url)
        self.exceptions = self.s3.meta.client.exceptions

    def create_bucket(self, bucket_name):
        bucket = self.s3.Bucket(bucket_name)
        bucket.create()

    def copy_bucket(self, source_bucket_name, destination_bucket_name):
        # TODO: compare this on a large project vs aws cli sync
        # http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Bucket.copy
        # for many small files it sounds like this may be slower
        source_bucket = self.s3.Bucket(source_bucket_name)
        destination_bucket = self.s3.Bucket(destination_bucket_name)
        for file_object in source_bucket.objects.all():
            destination_bucket.copy(CopySource={
                'Bucket': source_bucket_name,
                'Key': file_object.key
            }, Key=file_object.key)

    def delete_bucket(self, bucket_name):
        bucket = self.s3.Bucket(bucket_name)
        for key in bucket.objects.all():
            key.delete()
        bucket.delete()

    def grant_bucket_acl(self, bucket_name,
                         grant_full_control_user=None,
                         grant_read_user=None):
        bucket_acl = self.s3.BucketAcl(bucket_name)
        acl_args = self._make_acl_args(grant_full_control_user, grant_read_user)
        bucket_acl.put(**acl_args)

    def grant_objects_acl(self, bucket_name,
                          grant_full_control_user=None,
                          grant_read_user=None):
        acl_args = self._make_acl_args(grant_full_control_user, grant_read_user)
        keys = []
        bucket = self.s3.Bucket(bucket_name)
        for file_object in bucket.objects.all():
            keys.append(file_object.key)
            object_acl = self.s3.ObjectAcl(bucket_name, file_object.key)
            object_acl.put(**acl_args)

    @staticmethod
    def _make_acl_args(grant_full_control_user, grant_read_user):
        args = {}
        if grant_full_control_user:
            args['GrantFullControl'] = 'id={}'.format(grant_full_control_user.s3_id)
        if grant_read_user:
            args['GrantRead'] = 'id={}'.format(grant_read_user.s3_id)
        if not args:
            raise ValueError("Programmer should specify grant_full_control_user or grant_read_user")
        return args

    def get_bucket_owner(self, bucket_name):
        bucket_acl = self.s3.BucketAcl(bucket_name)
        return bucket_acl.owner['ID']


class S3BucketUtil(object):
    def __init__(self, endpoint, user):
        """
        :param endpoint: S3Endpoint: endpoint to connect to
        :param user: django user: user who we will act as
        """
        self.current_s3_user = S3User.objects.get(user=user, endpoint=endpoint)
        self.s3 = S3Resource(self.current_s3_user)

    @wrap_s3_exceptions
    def user_owns_bucket(self, bucket_name):
        """
         Return true if the bucket_name is in the list of buckets for the current user.
        :param bucket_name: str: name of the bucket to check
        :return: boolean: true if user owns the bucket
        """
        try:
            return self.s3.get_bucket_owner(bucket_name) == self.current_s3_user.s3_id
        except self.s3.exceptions.NoSuchBucket:
            raise S3NoSuchBucket("No such bucket found {}".format(bucket_name))
        except self.s3.exceptions.ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'AccessDenied':
                return False
            else:
                raise S3Exception(e)


class S3Exception(Exception):
    pass


class S3NoSuchBucket(S3Exception):
    pass


class S3DeliveryType:
    name = 's3'
    delivery_cls = S3Delivery
    transfer_in_background = True

    @staticmethod
    def make_delivery_details(*args):
        return S3DeliveryDetails(*args)

    @staticmethod
    def make_delivery_util(*args):
        return S3DeliveryUtil(*args)

    @staticmethod
    def transfer_delivery(delivery, _):
        delivery.mark_transferring()
        BackgroundFunctions.transfer_delivery(delivery.id)


class S3MessageFactory(MessageFactory):
    def __init__(self, s3_delivery, user):
        super(S3MessageFactory, self).__init__(
            S3DeliveryDetails(s3_delivery, user)
        )


class S3TransferOperation(object):
    """
    Object used in background process to run transfer steps and schedules next background step.
    """
    background_funcs = BackgroundFunctions

    def __init__(self, delivery_id):
        self.delivery = S3Delivery.objects.get(pk=delivery_id)
        self.to_user = self.delivery.to_user.user
        self.from_user = self.delivery.from_user.user

    def transfer_delivery_step(self):
        """
        Transfer delivery in s3 to recipient, schedules execution of notify_sender_delivery_accepted
        """
        print("Transferring s3 delivery {}".format(self.delivery.id))
        self.ensure_transferring()
        delivery_util = S3DeliveryUtil(self.delivery, self.from_user)
        delivery_util.accept_project_transfer()
        delivery_util.share_with_additional_users()
        warning_message = delivery_util.get_warning_message()
        self.background_funcs.notify_sender_delivery_accepted(self.delivery.id, warning_message)

    def notify_sender_delivery_accepted_step(self, warning_message):
        """
        Send email to the delivery sender that the transfer was accepted, schedules execution of
        notify_receiver_transfer_complete.
        :param warning_message: str: warning that may have occurred during the transfer operation
        """
        print("Notifying sender delivery {} has been accepted.".format(self.delivery.id))
        self.ensure_transferring()
        message = self.make_processed_message('accepted', warning_message)
        message.send()
        self.background_funcs.notify_receiver_transfer_complete(self.delivery.id, warning_message, message.email_text)

    def notify_receiver_transfer_complete_step(self, warning_message, sender_accepted_email_text):
        """
        Send email to the delivery recipient that the transfer was accepted, schedules execution of
        mark_delivery_complete.
        :param warning_message: str: warning that may have occurred during the transfer operation
        :param sender_accepted_email_text: str: text of email message sent to recipient
        """
        print("Notifying receiver transfer of delivery {} is complete.".format(self.delivery.id))
        self.ensure_transferring()
        message = self.make_processed_message('accepted_recipient', warning_message)
        message.send()
        self.background_funcs.mark_delivery_complete(self.delivery.id,
                                                     sender_accepted_email_text,
                                                     message.email_text)

    def mark_delivery_complete_step(self, sender_accepted_email_text, recipient_accepted_email_text):
        """
        Mark delivery as accepted and save email text sent to sender and recipient.
        This is the last step in transferring a delivery.
        :param sender_accepted_email_text: str: text of email message sent to sender
        :param recipient_accepted_email_text: str: text of email message sent to recipient
        """
        print("Marking delivery {} complete.".format(self.delivery.id))
        self.delivery.mark_accepted(self.to_user.get_username(),
                                    sender_accepted_email_text,
                                    recipient_accepted_email_text)

    def make_processed_message(self, process_type, warning_message):
        """
        Create email message based on email template settings for the delivery from user and process_type.
        :param process_type: str: name of the template to return
        :param warning_message: str: warning message from s3 transfer
        :return: utils.Message: email message
        """
        message_factory = S3MessageFactory(self.delivery, self.from_user)
        return message_factory.make_processed_message(process_type, warning_message=warning_message)

    def ensure_transferring(self):
        """
        Make sure the delivery is in transferring state since the background decorator retries after exceptions.
        """
        if self.delivery.state != State.TRANSFERRING:
            self.delivery.mark_transferring()
