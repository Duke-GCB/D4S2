from .oauth_utils import *
import logging

# Maps django User attributes to OIDC userinfo keys
USER_DETAILS_MAP = {
    'username': 'sub',
    'first_name': 'given_name',
    'last_name': 'family_name',
    'email': 'email',
}

USERNAME_KEY = USER_DETAILS_MAP.get('username')

logging.basicConfig()
logger = logging.getLogger(__name__)


class OAuth2Backend(object):

    @staticmethod
    def map_user_details(details):
        """
        Maps incoming user details from OIDC into a dict ready to instantiate a django user model
        :param details: dict containing keys e.g. sub, given_name, family_name, email
        :return: dict containing only keys valid for django user model
        """
        mapped = dict()
        for k, v in USER_DETAILS_MAP.items():
            if v in details:
                mapped[k] = details[v]
        return mapped

    def authenticate(self, service=None, token_dict=None):
        try:
            details = get_user_details(service, token_dict)
        except OAuthException as e:
            logger.error('Exception getting user details', e)
            return None
        details = self.map_user_details(details)
        if 'username' not in details:
            logger.error('Did not find username key in user details: {}'.format(details), )
            return None
        user, created = get_user_model().objects.get_or_create(**details)
        if created:
            # TODO: Fetch other details
            pass
        return user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
