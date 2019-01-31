from django.conf import settings
from ddsc.core.remotestore import RemoteStore
from d4s2_api.models import EmailTemplate, DDSDelivery, ShareRole, Share, UserEmailTemplateSet
from gcb_web_auth.backends.dukeds import make_auth_config
from gcb_web_auth.utils import get_dds_token, get_dds_config_for_credentials, get_default_dds_endpoint
from gcb_web_auth.models import DDSUserCredential
from ddsc.core.ddsapi import DataServiceError
from d4s2_api.utils import MessageFactory, MessageDirection

SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'

DDS_SERVICE_NAME = 'Duke Data Service'
PROJECT_ADMIN_ID = 'project_admin'
DDS_PERMISSIONS_ID_SEP = '_'


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
        endpoint = get_default_dds_endpoint()
        return '{}/#/project/{}'.format(endpoint.portal_root, project_id)

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

    def cancel_project_transfer(self, transfer_id):
        return self.remote_store.data_service.cancel_project_transfer(transfer_id)

    def share_project_with_user(self, project_id, dds_user_id, auth_role):
        return self.remote_store.data_service.set_user_project_permission(project_id, dds_user_id, auth_role)

    def get_users(self, full_name_contains=None, email=None, username=None):
        return self.remote_store.data_service.get_users(full_name_contains, email, username)

    def get_user(self, user_id):
        return self.remote_store.data_service.get_user_by_id(user_id)

    def get_projects(self):
        return self.remote_store.data_service.get_projects()

    def get_project(self, project_id):
        return self.remote_store.data_service.get_project_by_id(project_id)

    def get_current_user(self):
        return self.remote_store.get_current_user()

    def get_user_project_permission(self, project_id, user_id):
        return self.remote_store.data_service.get_user_project_permission(project_id, user_id).json()

    def get_project_permissions(self, project_id):
        return self.remote_store.data_service.get_project_permissions(project_id).json()

    def get_auth_providers(self):
        return self.remote_store.data_service.get_auth_providers().json()

    def get_auth_provider(self, auth_provider_id):
        return self.remote_store.data_service.get_auth_provider(auth_provider_id).json()

    def get_auth_provider_affiliates(self, auth_provider_id, full_name_contains=None, email=None, username=None):
        return self.remote_store.data_service.get_auth_provider_affiliates(auth_provider_id, full_name_contains, email, username).json()

    def get_auth_provider_affiliate(self, auth_provider_id, username):
        return self.remote_store.data_service.get_auth_provider_affiliate(auth_provider_id, username).json()

    def auth_provider_add_user(self, auth_provider_id, username):
        return self.remote_store.data_service.auth_provider_add_user(auth_provider_id, username).json()

    @staticmethod
    def get_openid_auth_provider_id():
        """
        Returns the locally-known (gcb_web_auth.DDSEndpoint) provider ID for the OpenID provider
        Affiliate lookups need a provider ID and we'll pretty much always use the same one
        :return:
        """
        endpoint = get_default_dds_endpoint()
        return endpoint.openid_provider_id


class DDSBase(object):
    @classmethod
    def from_list(cls, project_dicts):
        return [cls(p) for p in project_dicts]


class DDSUser(DDSBase):
    """
    A simple object to represent a DDSUser
    """

    def __init__(self, user_dict):
        self.id = user_dict.get('id')
        self.username = user_dict.get('username')
        self.full_name = user_dict.get('full_name')
        self.first_name = user_dict.get('first_name')
        self.last_name = user_dict.get('last_name')
        self.email = user_dict.get('email')

    @staticmethod
    def fetch_list(dds_util, full_name_contains, email, username):
        response = dds_util.get_users(full_name_contains, email, username).json()
        return DDSUser.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_user_id):
        response = dds_util.get_user(dds_user_id).json()
        return DDSUser(response)

    @staticmethod
    def get_or_register_user(dds_util, auth_provider_id, username):
        response = dds_util.get_users(username=username).json()
        if response['results']:
            return DDSUser(response['results'][0])
        else:
            response = dds_util.auth_provider_add_user(auth_provider_id, username)
            return DDSUser(response)


class DDSProject(DDSBase):
    """
    A simple object to represent a DDSProject
    """

    def __init__(self, project_dict):
        self.id = project_dict.get('id')
        self.name = project_dict.get('name')
        self.description = project_dict.get('description')
        self.is_deleted = project_dict.get('is_deleted')

    @staticmethod
    def fetch_list(dds_util):
        """
        Fetch list of DDSProjects based on dds_util.
        :param dds_util: DDSUtil
        :return: [DDSProjects]
        """
        response = dds_util.get_projects().json()
        return DDSProject.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_project_id):
        response = dds_util.get_project(dds_project_id).json()
        return DDSProject(response)


class DDSProjectPermissions(DDSBase):
    def __init__(self, project_permission_dict):
        self.project = project_permission_dict['project']['id']
        self.user = project_permission_dict['user']['id']
        self.auth_role = project_permission_dict['auth_role']['id']
        # The permission payload does not include a unique id. To work around this
        # below the project id and user id are combined to make a unique id.
        # There will only be one permission setting for each project/user.
        self.id = '{}{}{}'.format(self.project, DDS_PERMISSIONS_ID_SEP, self.user)

    @staticmethod
    def fetch_list(dds_util, project_id, user_id=None):
        """
        Fetch list of DDSProjects based on dds_util
        :param dds_util: DDSUtil
        :param project_id: str: DukeDS uuid of the project to get permissions for
        :param user_id: str: optional user id to filter
        :return: [ProjectPermissions]
        """
        if user_id:
            permissions = DDSProjectPermissions.fetch_one(dds_util, project_id, user_id)
            return [permissions]
        else:
            response = dds_util.get_project_permissions(project_id)
            return DDSProjectPermissions.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, project_id, user_id):
        response = dds_util.get_user_project_permission(project_id, user_id)
        return DDSProjectPermissions(response)


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
        self.email_template_set = delivery_or_share.email_template_set
        self.user = user

    def get_from_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.from_user_id)

    def get_to_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.to_user_id)

    def get_transfer_id(self):
        # self.delivery.transfer_id may
        # 1. be a non-empty string (for an existing delivery with a transfer_id)
        # 2. be '' or None (for a delivery preview)
        # 3. not exist at all (for a share email)
        # For case 1, return the transfer_id. For 2 and 3, return an empty string.
        try:
            transfer_id = self.delivery.transfer_id
            return transfer_id or ''
        except AttributeError:
            return ''

    def get_project(self):
        # Fetch a DDSProject, by transfer_id if present
        transfer_id = self.get_transfer_id()
        if transfer_id:
            transfer = DDSProjectTransfer.fetch_one(self.ddsutil, transfer_id)
            return DDSProject(transfer.project_dict)
        else:
            return DDSProject.fetch_one(self.ddsutil, self.delivery.project_id)

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.delivery.project_id)

    def get_user_message(self):
        return self.delivery.user_message

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
            base_context = self.get_context()
            user_message = self.get_user_message()
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))

        return {
            'service_name': base_context['service_name'],
            'project_name': base_context['project_title'],
            'recipient_name': base_context['to_name'],
            'recipient_email': base_context['to_email'],
            'sender_email': base_context['from_email'],
            'sender_name': base_context['from_name'],
            'project_url': base_context['project_url'],
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
        transfer_id = self.get_transfer_id()

        return {
            'service_name': DDS_SERVICE_NAME,
            'transfer_id': transfer_id,
            'from_name': from_user.full_name,
            'from_email': from_user.email,
            'to_name': to_user.full_name,
            'to_email': to_user.email,
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

    def give_sender_permission(self, share_role=ShareRole.DOWNLOAD):
        """
        Give delivery sending user share_role permissions for the delivered project.
        Adds user to failed_share_users if unable to grant sender permissions.
        :param share_role: str: role to give to the user defaults to file_downloader
        """
        project_id = self.delivery.project_id
        from_user_id = self.delivery.from_user_id
        try:
            self.dds_util.share_project_with_user(project_id, from_user_id, share_role)
        except DataServiceError:
            self.failed_share_users.append(self._try_lookup_user_name(from_user_id))

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
                                     user_message=self.share_user_message,
                                     email_template_set=self.delivery.email_template_set)
        message_factory = DDSMessageFactory(share, self.user)
        message = message_factory.make_share_message()
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
    def transfer_delivery(delivery, user):
        delivery_util = DDSDeliveryType.make_delivery_util(delivery, user)
        delivery_util.accept_project_transfer()
        delivery_util.share_with_additional_users()
        delivery_util.give_sender_permission()
        warning_message = delivery_util.get_warning_message()
        message_factory = DDSMessageFactory(delivery, user)
        sender_message = message_factory.make_processed_message('accepted',
                                                                MessageDirection.ToSender,
                                                                warning_message=warning_message)
        sender_message.send()
        recipient_message = message_factory.make_processed_message('accepted_recipient',
                                                                   MessageDirection.ToRecipient)
        recipient_message.send()
        delivery.mark_accepted(user.get_username(), sender_message.email_text, recipient_message.email_text)
        return warning_message

    @staticmethod
    def make_processed_message(delivery, user, process_type, direction, warning_message=''):
        message_factory = DDSMessageFactory(delivery, user)
        return message_factory.make_processed_message(process_type, direction, warning_message=warning_message)


class DDSMessageFactory(MessageFactory):
    def __init__(self, delivery, user):
        super(DDSMessageFactory, self).__init__(
            DeliveryDetails(delivery, user)
        )


class DDSAuthProvider(DDSBase):
    """
    A simple object to represent a DDSAuthProvider
    """
    def __init__(self, provider_dict):
        self.id = provider_dict.get('id')
        self.service_id = provider_dict.get('service_id')
        self.name = provider_dict.get('name')
        self.is_deprecated = provider_dict.get('is_deprecated')
        self.is_default = provider_dict.get('is_default')
        self.login_initiation_url = provider_dict.get('login_initiation_url')

    @staticmethod
    def fetch_list(dds_util):
        response = dds_util.get_auth_providers()
        return DDSAuthProvider.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_provider_id):
        response = dds_util.get_auth_provider(dds_provider_id)
        return DDSAuthProvider(response)


class DDSAffiliate(DDSBase):
    """
    A simple object to represent a DDSAffiliate
    """
    def __init__(self, project_dict):
        self.uid = project_dict.get('uid')
        self.full_name = project_dict.get('full_name')
        self.first_name = project_dict.get('first_name')
        self.last_name = project_dict.get('last_name')
        self.email = project_dict.get('email')

    @staticmethod
    def fetch_list(dds_util, auth_provider_id, full_name_contains, email, username):
        """
        Fetch list of DDSAffiliates for an auth_provider, filtered by name, email, or username
        :param dds_util: DDSUtil
        :param auth_provider_id: ID of a DDS Auth provider
        :param full_name_contains: Search string for user's full name or None
        :param email: Email address to search or None
        :param username: username to search or None
        :return: [DDSAffiliate]
        """
        response = dds_util.get_auth_provider_affiliates(auth_provider_id, full_name_contains, email, username)
        return DDSAffiliate.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, auth_provider_id, uid):
        """
        Fetch a single DDSAffiliate for an auth provider by unique username (uid)
        :param dds_util: DDSUtil
        :param auth_provider_id: ID of a DDS Auth provider
        :param uid: Unique username for which to fetch affiliate
        :return:
        """
        response = dds_util.get_auth_provider_affiliate(auth_provider_id, uid)
        return DDSAffiliate(response)
