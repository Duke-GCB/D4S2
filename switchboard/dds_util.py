from django.conf import settings
from ddsc.core.remotestore import RemoteStore
from d4s2_api.models import EmailTemplate, DDSDelivery, ShareRole, Share
from gcb_web_auth.backends.dukeds import make_auth_config
from gcb_web_auth.utils import get_dds_token, get_dds_config_for_credentials
from gcb_web_auth.models import DDSEndpoint, DDSUserCredential
from d4s2_api.utils import BaseShareMessage, BaseDeliveryMessage, BaseProcessedMessage
from ddsc.core.ddsapi import DataServiceError


SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'


class DDSUtil(object):
    def __init__(self, user):
        if not user:
            raise ValueError('DDSUtil requires a user')
        self.user = user
        self._remote_store = None

    @property
    def remote_store(self):
        if self._remote_store is None:
            # First need to resolve DukeDS Credential.
            # For simplicity and development ease, we first check if a DDSUserCredential exists for the requesting user
            try:
                dds_credential = DDSUserCredential.objects.get(user=self.user)
                config = get_dds_config_for_credentials(dds_credential)
            except DDSUserCredential.DoesNotExist:
                # No DDSUserCredential configured for this user, fall back to OAuth
                # May raise an OAuthConfigurationException
                dds_token = get_dds_token(self.user)
                config = make_auth_config(dds_token.key)
            self._remote_store = RemoteStore(config)
        return self._remote_store

    def get_remote_user(self, user_id):
        return self.remote_store.fetch_user(user_id)

    def get_remote_project(self, project_id):
        return self.remote_store.fetch_remote_project_by_id(project_id)

    def get_remote_project_with_children(self, project_id):
        project = self.get_remote_project(project_id)
        return self.remote_store.fetch_remote_project(project.name, must_exist=True)

    def get_project_url(self, project_id):
        endpoint = DDSEndpoint.objects.first()
        return '{}/portal/#/project/{}'.format(endpoint.portal_root, project_id)

    def add_user(self, user_id, project_id, auth_role):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.set_user_project_permission(project, user, auth_role)

    def remove_user(self, user_id, project_id):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.revoke_user_project_permission(project, user)

    def get_project_transfer(self, transfer_id):
        return self.remote_store.data_service.get_project_transfer(transfer_id)

    def get_project_transfers(self):
        return self.remote_store.data_service.get_all_project_transfers()

    def create_project_transfer(self, project_id, to_user_ids):
        return self.remote_store.data_service.create_project_transfer(project_id, to_user_ids).json()

    def accept_project_transfer(self, transfer_id):
        return self.remote_store.data_service.accept_project_transfer(transfer_id).json()

    def decline_project_transfer(self, transfer_id, reason):
        return self.remote_store.data_service.reject_project_transfer(transfer_id, reason).json()

    def share_project_with_user(self, project_id, dds_user_id, auth_role):
        return self.remote_store.data_service.set_user_project_permission(project_id, dds_user_id, auth_role)

    def get_users(self, full_name_contains=None):
        if full_name_contains:
            return self.remote_store.data_service.get_users_by_full_name(full_name_contains)
        else:
            return self.remote_store.data_service.get_all_users()

    def get_user(self, user_id):
        return self.remote_store.data_service.get_user_by_id(user_id)

    def get_projects(self):
        return self.remote_store.data_service.get_projects()

    def get_project(self, project_id):
        return self.remote_store.data_service.get_project_by_id(project_id)

    def get_current_user(self):
        return self.remote_store.get_current_user()


class DDSBase(object):
    @classmethod
    def from_list(cls, project_dicts):
        return [cls(p) for p in project_dicts]


class DDSUser(DDSBase):
    """
    A simple object to represent a DDSProject
    """

    def __init__(self, user_dict):
        self.id = user_dict.get('id')
        self.username = user_dict.get('username')
        self.full_name = user_dict.get('full_name')
        self.first_name = user_dict.get('first_name')
        self.last_name = user_dict.get('last_name')
        self.email = user_dict.get('email')

    @staticmethod
    def fetch_list(dds_util, full_name_contains):
        response = dds_util.get_users(full_name_contains).json()
        return DDSUser.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_user_id):
        response = dds_util.get_user(dds_user_id).json()
        return DDSUser(response)


class DDSProject(DDSBase):
    """
    A simple object to represent a DDSProject
    """

    def __init__(self, project_dict):
        self.id = project_dict.get('id')
        self.name = project_dict.get('name')
        self.description = project_dict.get('description')

    @staticmethod
    def fetch_list(dds_util):
        response = dds_util.get_projects().json()
        return DDSProject.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_project_id):
        response = dds_util.get_project(dds_project_id).json()
        return DDSProject(response)


class DDSProjectTransfer(DDSBase):

    def __init__(self, transfer_dict):
        self.id = transfer_dict.get('id')
        self.status = transfer_dict.get('status')
        self.status_comment = transfer_dict.get('status_comment')
        self.to_users = DDSUser.from_list(transfer_dict.get('to_users'))
        self.from_user = DDSUser(transfer_dict.get('from_user'))
        self.project = DDSProject(transfer_dict.get('project'))
        self.project_dict = transfer_dict.get('project')
        self.delivery = DDSProjectTransfer._lookup_delivery_id(self.id)

    @staticmethod
    def _lookup_delivery_id(transfer_id):
        delivery = DDSDelivery.objects.filter(transfer_id=transfer_id).first()
        if delivery:
            return delivery.id
        return None

    @staticmethod
    def fetch_list(dds_util):
        response = dds_util.get_project_transfers().json()
        return DDSProjectTransfer.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_project_transfer_id):
        response = dds_util.get_project_transfer(dds_project_transfer_id).json()
        return DDSProjectTransfer(response)


class DeliveryDetails(object):
    def __init__(self, delivery_or_share, user):
        self.delivery = delivery_or_share
        self.ddsutil = DDSUtil(user)
        self.user = user

    def get_from_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.from_user_id)

    def get_to_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.to_user_id)

    def get_project(self):
        transfer = DDSProjectTransfer.fetch_one(self.ddsutil, self.delivery.transfer_id)
        return DDSProject(transfer.project_dict)

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.delivery.project_id)

    def get_user_message(self):
        return self.delivery.user_message

    def get_share_template_text(self):
        email_template = EmailTemplate.for_share(self.delivery, self.user)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')

    def get_action_template_text(self, action_name):
        email_template = EmailTemplate.for_user(self.user, action_name)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')

    def get_delivery(self):
        return self.delivery

    @classmethod
    def from_transfer_id(self, transfer_id, user):
        """
        Builds DeliveryDetails based on DukeDS transfer id
        :param transfer_id: a DukeDS Project Transfer ID
        :param user: a Django user with related DukeDS credentials
        :return: DeliveryDetails
        """
        delivery = DDSDelivery.objects.get(transfer_id=transfer_id)
        return DeliveryDetails(delivery, user)

    def get_email_context(self, accept_url, process_type, reason, warning_message=''):
        try:
            sender = self.get_from_user()
            receiver = self.get_to_user()
            project = self.get_project()
            project_url = self.get_project_url()
            user_message = self.get_user_message()
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))

        return {
            'project_name': project.name,
            'recipient_name': receiver.full_name,
            'recipient_email': receiver.email,
            'sender_email': sender.email,
            'sender_name': sender.full_name,
            'project_url': project_url,
            'accept_url': accept_url,
            'type': process_type,  # accept or decline
            'message': reason,  # decline reason
            'user_message': user_message,
            'warning_message': warning_message,
        }

    def get_context(self):
        from_user = self.get_from_user()
        to_user = self.get_to_user()
        project = self.get_project()
        project_url = self.get_project_url()
        return {
            'service': 'Duke Data Service',
            'transfer_id': str(self.delivery.transfer_id),
            'from_name': from_user.full_name,
            'from_email': from_user.email,
            'to_name': to_user.full_name,
            'project_title': project.name,
            'project_url': project_url
        }


class DeliveryUtil(object):
    """
    Communicates with DukeDS via DDSUtil to accept the project transfer.
    Also gives download permission to the users in the delivery's share_to_users list.
    """
    def __init__(self, delivery, user, share_role, share_user_message):
        """
        :param delivery: A Delivery object
        :param user: The user with a DukeDS authentication credential
        :param share_role: str: share role to use for additional users
        :param share_user_message: str: reason for sharing to this user
        """
        self.delivery = delivery
        self.user = user
        self.dds_util = DDSUtil(user)
        self.share_role = share_role
        self.share_user_message = share_user_message
        self.failed_share_users = []

    def accept_project_transfer(self):
        """
        Communicate with DukeDS via to accept the project transfer.
        """
        self.dds_util.accept_project_transfer(self.delivery.transfer_id)

    def share_with_additional_users(self):
        """
        Share project with additional users based on delivery share_to_users.
        Adds user names to failed_share_users for failed share commands.
        """
        for share_to_user in self.delivery.share_users.all():
            self._share_with_additional_user(share_to_user)

    def _share_with_additional_user(self, share_to_user):
        try:
            project_id = self.delivery.project_id
            self.dds_util.share_project_with_user(project_id, share_to_user.dds_id, self.share_role)
            self._create_and_send_share_message(share_to_user, project_id)
        except DataServiceError:
            self.failed_share_users.append(self._try_lookup_user_name(share_to_user.dds_id))

    def _try_lookup_user_name(self, user_id):
        try:
            remote_user = self.dds_util.get_remote_user(user_id)
            return remote_user.full_name
        except DataServiceError:
            return user_id

    def _create_and_send_share_message(self, share_to_user, project_id):
        share = Share.objects.create(project_id=project_id,
                                     from_user_id=self.delivery.to_user_id,
                                     to_user_id=share_to_user.dds_id,
                                     role=self.share_role,
                                     user_message=self.share_user_message)
        message = DDSShareMessage(share, self.user)
        message.send()
        share.mark_notified(message.email_text)

    def get_warning_message(self):
        """
        Create message about any issues that occurred during share_with_additional_users.
        :return: str: end user warning message
        """
        failed_share_users_str = ', '.join(self.failed_share_users)
        warning_message = ''
        if failed_share_users_str:
            warning_message = "Failed to share with the following user(s): " + failed_share_users_str
        return warning_message

    def decline_delivery(self, reason):
        """
        Decline the delivery through dds_util, supplying the reason provided
        :param reason: The reason the user is declining the delivery
        :return: None
        """
        try:
            self.dds_util.decline_project_transfer(self.delivery.transfer_id, reason)
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))


class DDSDeliveryType:
    name = 'dds'
    delivery_cls = DDSDelivery
    transfer_in_background = False

    @staticmethod
    def make_delivery_details(*args):
        return DeliveryDetails(*args)

    @staticmethod
    def make_delivery_util(*args):
        return DeliveryUtil(*args,
                            share_role=ShareRole.DOWNLOAD,
                            share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)

    @staticmethod
    def make_processed_message(*args, **kwargs):
        return DDSProcessedMessage(*args, **kwargs)

    @staticmethod
    def transfer_delivery(delivery, user):
        delivery_util = DDSDeliveryType.make_delivery_util(delivery, user)
        delivery_util.accept_project_transfer()
        delivery_util.share_with_additional_users()
        warning_message = delivery_util.get_warning_message()
        message = DDSDeliveryType.make_processed_message(delivery, user, 'accepted',
                                                         warning_message=warning_message)
        message.send()
        delivery.mark_accepted(user.get_username(), message.email_text)
        return warning_message


class DDSMessage(object):
    @staticmethod
    def make_delivery_details(deliverable, user):
        return DeliveryDetails(deliverable, user)


class DDSShareMessage(DDSMessage, BaseShareMessage):
    pass


class DDSDeliveryMessage(DDSMessage, BaseDeliveryMessage):
    pass


class DDSProcessedMessage(DDSMessage, BaseProcessedMessage):
    pass
