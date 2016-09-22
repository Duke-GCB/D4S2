from ddsc.config import Config
from django.conf import settings
from ddsc.core.remotestore import RemoteStore
from handover_api.models import DukeDSUser, EmailTemplate, EmailTemplateException


class DDSUtil(object):
    def __init__(self, user_id):
        self.sender_user_id = user_id
        self._remote_store = None

    @property
    def remote_store(self):
        if self._remote_store is None:
            user = DukeDSUser.api_users.get(dds_id=self.sender_user_id)
            config = Config()
            config.update_properties(settings.DDSCLIENT_PROPERTIES)
            config.update_properties({'user_key': user.api_key})
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
        portal_root = settings.DDSCLIENT_PROPERTIES['portal_root']
        return '{}/portal/#/project/{}'.format(portal_root, project_id)

    def add_user(self, user_id, project_id, auth_role):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.set_user_project_permission(project, user, auth_role)

    def remove_user(self, user_id, project_id):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.revoke_user_project_permission(project, user)


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


class HandoverDetails(object):
    def __init__(self, handover_or_share):
        self.handover = handover_or_share
        self.ddsutil = DDSUtil(self.handover.from_user.dds_id)
        self.model_populator = ModelPopulator(self.ddsutil)

    def get_from_user(self):
        self.model_populator.populate_user(self.handover.from_user)
        return self.handover.from_user

    def get_to_user(self):
        self.model_populator.populate_user(self.handover.to_user)
        return self.handover.to_user

    def get_project(self):
        self.model_populator.populate_project(self.handover.project)
        return self.handover.project

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.handover.project.project_id)

    def get_share_template_text(self):
        email_template = EmailTemplate.for_share(self.handover)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')

    def get_action_template_text(self, action_name):
        email_template = EmailTemplate.by_action(self.handover, action_name)
        if email_template:
            return email_template.subject, email_template.body
        else:
            raise RuntimeError('No email template found')
