from gcb_web_auth.dukeds_auth import DukeDSTokenAuthentication
from gcb_web_auth.backends.dukeds import DukeDSAuthBackend
from gcb_web_auth.backends.base import BaseBackend
from models import DukeDSUser


class D4S2DukeDSTokenAuthentication(DukeDSTokenAuthentication):
    """
    Extends authorization to save users to DukeDSUser
    """
    def __init__(self):
        self.backend = DukeDSAuthBackend()


class D4S2DukeDSAuthBackend(DukeDSAuthBackend):
    """
    Backend for DukeDS Auth that save users to DukeDSUser
    Conveniently, the keys used by DukeDS user objects are a superset of the django ones,
    so we rely on the filtering in the base class
    """
    def __init__(self, save_tokens=True, save_dukeds_users=True):
        super(D4S2DukeDSAuthBackend, self).__init__(save_tokens, save_dukeds_users)
        self.save_tokens = save_tokens
        self.save_dukeds_users = save_dukeds_users
        self.failure_reason = None

    def save_dukeds_user(self, user, raw_user_dict):
        user_dict = DukeDSAuthBackend.harmonize_dukeds_user_details(raw_user_dict)
        dukeds_user, created = DukeDSUser.objects.get_or_create(user=user,
                                                                dds_id=raw_user_dict.get('id'))
        if created:
            BaseBackend.update_model(dukeds_user, user_dict)
