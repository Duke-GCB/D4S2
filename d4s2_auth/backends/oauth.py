from ..oauth_utils import *
from .base import BaseBackend
import logging

# Maps django User attributes to OIDC userinfo keys

logging.basicConfig()
logger = logging.getLogger(__name__)


class OAuth2Backend(BaseBackend):

    def get_user_details_map(self):
        """
        Map of django user model keys to the OIDC OAuth keys
        :return:
        """
        return {
            'username': 'sub',
            'first_name': 'given_name',
            'last_name': 'family_name',
            'email': 'email',
        }

    def authenticate(self, service=None, token_dict=None):
        try:
            details = user_details_from_token(service, token_dict)
        except OAuthException as e:
            logger.error('Exception getting user details', e)
            return None
        user = self.save_user(details)
        return user
