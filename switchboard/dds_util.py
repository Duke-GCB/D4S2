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

