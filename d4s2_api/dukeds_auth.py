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
