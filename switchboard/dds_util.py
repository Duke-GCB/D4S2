from ddsc.config import Config
from django.conf import settings
from ddsc.core.remotestore import RemoteStore
from handover_api.models import DukeDSUser


class DDSUtil(object):
    def __init__(self, user_id):
        self.sender_user_id = user_id
        self._remote_store = None

    @property
    def remote_store(self):
        if self._remote_store is None:
            user = DukeDSUser.objects.get(dds_id=self.sender_user_id)
            config = Config()
            config.update_properties(settings.DDSCLIENT_PROPERTIES)
            config.update_properties({'user_key': user.api_key})
            self._remote_store = RemoteStore(config)
        return self._remote_store

    def get_remote_user(self, user_id):
        return self.remote_store.fetch_user(user_id)

    def get_remote_project(self, project_id):
        return self.remote_store.fetch_remote_project_by_id(project_id)

    def get_project_url(self, project_id):
        return 'https://{}/portal/#/project/{}'.format(self.remote_store.config.get_url_base(), project_id)

    def add_user(self, user_id, project_id, auth_role):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.set_user_project_permission(project, user, auth_role)

    def remove_user(self, user_id, project_id):
        project = self.remote_store.fetch_remote_project_by_id(project_id)
        user = self.remote_store.fetch_user(user_id)
        self.remote_store.revoke_user_project_permission(project, user)

class HandoverDetails(object):
    def __init__(self, handover_or_draft):
        self.handover = handover_or_draft
        self.ddsutil = DDSUtil(self.handover.from_user_id)

    def get_from_user(self):
        return self.ddsutil.get_remote_user(self.handover.from_user_id)

    def get_to_user(self):
        return self.ddsutil.get_remote_user(self.handover.to_user_id)

    def get_project(self):
        return self.ddsutil.get_remote_project(self.handover.project_id)

    def get_project_url(self):
        return self.ddsutil.get_project_url(self.handover.project_id)

    def transfer_project(self):
        # Pretend I transfer the project
        pass
