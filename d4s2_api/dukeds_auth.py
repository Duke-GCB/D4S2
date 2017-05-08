from gcb_web_auth.dukeds_auth import DukeDSTokenAuthentication
from gcb_web_auth.backends.dukeds import DukeDSAuthBackend
from gcb_web_auth.backends.base import BaseBackend
from gcb_web_auth.backends.oauth import OAuth2Backend
from .models import DukeDSUser


class D4S2DukeDSAuthBackend(DukeDSAuthBackend):
    """
    DukeDSAuthBackend that updates a local user model with D4S2 details on creation
    """

    def handle_new_user(self, user, details):
        user_dict = DukeDSAuthBackend.harmonize_dukeds_user_details(details)
        dukeds_user, created = DukeDSUser.objects.get_or_create(dds_id=details.get('id'))
        dukeds_user.user = user
        dukeds_user.save()
        if created:
            BaseBackend.update_model(dukeds_user, user_dict)


class D4S2DukeDSTokenAuthentication(DukeDSTokenAuthentication):
    """
    Extends authorization to save users to DukeDSUser
    """
    def __init__(self):
        self.backend = D4S2DukeDSAuthBackend()


class D4S2OAuth2Backend(OAuth2Backend):
    """
    Slight customization to connect User objects to existing DukeDSUser objects (by email)
    """
    def handle_new_oauth_user(self, user, details):
        """
        When saving a new user from OAuth, check to see if an unlinked DukeDSUser object exists, and link it
        :param user: A django user, created after receiving OAuth details
        :param details: A dictionary of OAuth user info
        :return: None
        """
        try:
            dukeds_user = DukeDSUser.objects.get(user=None, email=user.email)
            dukeds_user.user = user
            dukeds_user.save()
        except DukeDSUser.DoesNotExist:
            # Either user already linked or not found. Either way, don't do anything.
            pass
