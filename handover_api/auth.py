from rest_framework import authentication
from rest_framework import exceptions
from handover_api.models import DukeDSUser
from django.utils.translation import ugettext_lazy as _

class APIKeyTokenAuthentication(authentication.TokenAuthentication):
    """
    Simple token based authentication, using api_key on the DukeDSUser model

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Token ".  For example:

        Authorization: Token 401f7ac837da42b97f613d789819ff93537bee6a
    """

    def authenticate_credentials(self, key):
        try:
            token = DukeDSUser.api_users.select_related('user').get(api_key=key)
        except DukeDSUser.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        return (token.user, token)
