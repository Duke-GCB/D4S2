from django.conf import settings
from ddsc.core.remotestore import RemoteStore
from d4s2_api.models import EmailTemplate, Delivery
from gcb_web_auth.backends.dukeds import make_auth_config
from gcb_web_auth.utils import get_dds_token
from gcb_web_auth.models import DukeDSSettings


class DDSUtil(object):
    def __init__(self, user):
        if not user:
            raise ValueError('DDSUtil requires a user')
        self.user = user
        self._remote_store = None

    @property
    def remote_store(self):
        if self._remote_store is None:
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
        duke_ds_settings = DukeDSSettings.objects.first()
        return '{}/portal/#/project/{}'.format(duke_ds_settings.portal_root, project_id)

    def add_user(self, user_id, project_id, auth_role):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.set_user_project_permission(project, user, auth_role)

    def remove_user(self, user_id, project_id):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.revoke_user_project_permission(project, user)

    def get_project_transfer(self, transfer_id):
        return self.remote_store.data_service.get_project_transfer(transfer_id).json()

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
    def fetch_one(dds_util, dds_user_id):
        response = dds_util.get_project(dds_user_id).json()
        return DDSProject(response)


class DeliveryDetails(object):
    def __init__(self, delivery_or_share, user):
        self.delivery = delivery_or_share
        self.ddsutil = DDSUtil(user)

    def get_from_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.from_user_id)

    def get_to_user(self):
        return DDSUser.fetch_one(self.ddsutil, self.delivery.to_user_id)

    def get_project(self):
        return DDSProject.fetch_one(self.ddsutil, self.delivery.project_id)

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.delivery.project_id)

    def get_user_message(self):
        return self.delivery.user_message

    def get_share_template_text(self):
        email_template = EmailTemplate.for_share(self.delivery)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')

    def get_action_template_text(self, action_name):
        email_template = EmailTemplate.for_operation(self.delivery, action_name)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')

    def get_delivery(self):
        return self.delivery

    @classmethod
    def from_transfer_id(self, transfer_id, user):
        """
        Finds a local delivery by transfer id and ensures it's up-to-date with the server
        :param transfer_id: a DukeDS Project Transfer ID
        :param user: a Django user with related DukeDS credentials
        :return: a d4s2_api.models.Delivery
        """

        delivery = Delivery.objects.get(transfer_id=transfer_id)
        return DeliveryDetails(delivery, user)
