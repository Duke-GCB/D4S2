from rest_framework import authentication
from rest_framework import exceptions
from d4s2_api.models import DukeDSUser
from django.utils.translation import ugettext_lazy as _


# TODO: Finish implementing this and add it to settings_base
class DukeDSTokenAuthentication(authentication.TokenAuthentication):

    """
    Token-based authentication, verifying the token with the DukeDS get_current_user endpoint

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Token ".  For example:

        Authorization: Token 401f7ac837da42b97f613d789819ff93537bee6a
    """

    def authenticate_credentials(self, key):
        try:
            # Search our model for this token
            # if found, make sure not expired
                # If expired, FAIL
                # If not expired, succeed
            # if not found, check with DukeDS
                # if ok, save and succeed
                # if not ok, FAIL
            # token = DukeDSUser.objects.select_related('user').get(api_key=key)
            raise exceptions.AuthenticationFailed(_('Not implemented.'))
        except DukeDSUser.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        return (token.user, token)
