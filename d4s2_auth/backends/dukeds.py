from .base import BaseBackend
from ddsc.core.ddsapi import DataServiceApi, DataServiceAuth
from ddsc.config import Config
from django.conf import settings
from requests.exceptions import HTTPError

class DukeDSAuthBackend(BaseBackend):
    """
    Backend for DukeDS Auth
    Conveniently, the keys used by DukeDS user objects are a superset of the django ones,
    so we rely on the filtering in the base class
    """

    @staticmethod
    def make_config(token):
        """
        Returns a DukeDS config object populated with URL and such
        from this application's django settings
        :param token: The authorization token for DukeDS
        :return: a ddsc.config.Config
        """
        config = Config()
        config.update_properties(settings.DDSCLIENT_PROPERTIES)
        config.values[Config.AUTH] = token
        return config

    def map_user_details(self, details):
        details = super(DukeDSAuthBackend, self).map_user_details(details)
        # For DukeDS, we need to append @duke.edu to username
        if 'username' in details:
            details['username'] = '{}@duke.edu'.format(details['username'])
        return details

    def authenticate(self, token):
        """
        Bears the token to DukeDS current_user API to authenticate
        :param token: presented as Authorization: <token>
        :return: an authenticated, populated user if found, or None if not.
        """
        config = self.make_config(token)
        auth = DataServiceAuth(config)
        api = DataServiceApi(auth, config.url)
        try:
            response = api.get_current_user()
            response.raise_for_status()
            user_dict = response.json()
        except HTTPError as e:
            return None
        user = self.save_user(user_dict)
        # Also record a duke DS User!
        return user
