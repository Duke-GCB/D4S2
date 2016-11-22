from oauth_utils import *
import logging

USERNAME_KEY = 'sub'
logging.basicConfig()
logger = logging.getLogger(__name__)


class OAuth2Backend(object):

    def authenticate(self, service=None, token_dict=None):
        try:
            user_details = get_user_details(service, token_dict)
        except OAuthException as e:
            logger.error('Exception getting user details', e)
            return None
        if USERNAME_KEY not in user_details:
            logger.error('Did not find username key in user details: {}'.format(user_details), )
            return None
        user, created = get_user_model().objects.get_or_create(username=user_details.get(USERNAME_KEY))
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
