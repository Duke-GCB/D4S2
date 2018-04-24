from d4s2_api.models import S3Delivery, EmailTemplate, S3User, S3UserTypes
from d4s2_api.utils import ProcessedMessage, DeliveryMessage
import boto3


class S3DeliveryUtil(object):
    def __init__(self, s3_delivery, user):
        self.s3_delivery = s3_delivery
        self.endpoint = s3_delivery.bucket.endpoint
        self.source_bucket_name = s3_delivery.bucket.name
        self.user = user
        self.s3_agent = S3User.objects.get(type=S3UserTypes.AGENT, endpoint=self.endpoint)
        self.current_s3_user = S3User.objects.get(user=self.user, endpoint=self.endpoint)
        self.destination_bucket_name = 'delivery_{}'.format(self.source_bucket_name)

    def give_agent_permissions(self):
        s3 = S3Resource(self.current_s3_user)
        s3.grant_bucket_acl(self.source_bucket_name,
                            grant_full_control_user=self.s3_agent)
        print("Gave agent {} Full Control".format(self.s3_agent.s3_id))

    def accept_project_transfer(self):
        self._grant_user_read_permissions(self.s3_delivery.to_user)
        self._copy_files_to_new_destination_bucket()
        self._cleanup_source_bucket()

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

    def decline_delivery(self):
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
            'transfer_id': str(self.s3_delivery.transfer_id),
            'from_name': '{} {}'.format(from_user.first_name, from_user.last_name),
            'from_email': from_user.email,
            'to_name': '{} {}'.format(to_user.first_name, to_user.last_name),
            'to_email': to_user.email,
            'project_title': bucket_name,
            'project_url': 's://{}'.format(bucket_name)
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
        }

    @staticmethod
    def from_s3_delivery_id(s3_delivery_id, user):
        """
        :param s3_delivery_id: int: S3Delivery id
        :param user: django user
        :return: S3DeliveryDetails
        """
        delivery = S3Delivery.objects.get(pk=s3_delivery_id)
        return S3DeliveryDetails(delivery, user)

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


class S3ProcessedMessage(ProcessedMessage):
    def make_delivery_details(self, deliverable, user):
        return S3DeliveryDetails(deliverable, user)


class S3DeliveryMessage(DeliveryMessage):
    def make_delivery_details(self, deliverable, user):
        return S3DeliveryDetails(deliverable, user)
