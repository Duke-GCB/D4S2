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


class ModelPopulator(object):
    """
    Populates local models from DukeDS API
    """
    def __init__(self, dds_util):
        self.dds_util = dds_util

    def populate_user(self, dds_user):
        """
        Populates a DukeDSUser calling the DukeDS API if needed
        :param dds_user: A DukeDSUser model object that has been saved, but may not be populated
        :return: None
        """
        if not dds_user.populated():
            remote_user = self.dds_util.get_remote_user(dds_user.dds_id)
            dds_user.email = dds_user.email or remote_user.email
            dds_user.full_name = dds_user.full_name or remote_user.full_name
            dds_user.save()

    def populate_project(self, dds_project):
        """
        Populates a DukeDSProjectcalling the DukeDS API if needed
        :param dds_user:
        :return: None
        """
        if not dds_project.populated():
            remote_project = self.dds_util.get_remote_project(dds_project.project_id)
            dds_project.name = dds_project.name or remote_project.name
            dds_project.save()

    def update_delivery(self, delivery):
        project_transfer = self.dds_util.get_project_transfer(delivery.transfer_id)
        delivery.update_state_from_project_transfer(project_transfer)


class DeliveryDetails(object):
    def __init__(self, delivery_or_share, user):
        self.delivery = delivery_or_share
        self.ddsutil = DDSUtil(user)
        self.model_populator = ModelPopulator(self.ddsutil)

    def get_from_user(self):
        self.model_populator.populate_user(self.delivery.from_user)
        return self.delivery.from_user

    def get_to_user(self):
        self.model_populator.populate_user(self.delivery.to_user)
        return self.delivery.to_user

    def get_project(self):
        self.model_populator.populate_project(self.delivery.project)
        return self.delivery.project

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.delivery.project.project_id)

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
        self.model_populator.update_delivery(self.delivery)
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
