from rest_framework import authentication
from rest_framework import exceptions
from d4s2_api.models import DukeDSUser
from d4s2_auth.models import DukeDSAPIToken
from django.utils.translation import ugettext_lazy as _
from .backends.dukeds import get_local_token, DukeDSAuthBackend


class DukeDSTokenAuthentication(authentication.BaseAuthentication):

    """
    DukeDS api_token authentication, verifying the token with the DukeDS get_current_user endpoint

    Clients should authenticate by passing the token key in the "X_DukeDS_Authorization" HTTP header

    For example:

        X_DukeDS_Authorization: abcd.ef123.4567

        Can change the expected header, should probably do that
    """
    request_auth_header = 'X_DukeDS_Authorization'

    def __init__(self):
        self.backend = DukeDSAuthBackend()

    def authenticate(self, request):
        auth = request.META.get(self.request_auth_header)
        if not auth:
            msg = _('Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        try:
            token = auth.decode()
        except UnicodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)
        return self.authenticate_credentials(token)

    def authenticate_credentials(self, key):
        # Heavily leverages the backend's authenticate() method, which
        # makes API calls to DukeDS to validate tokens and fetch/populate users
        # It returns a user or None. And if it returns None, we should check the reason
        user = self.backend.authenticate(key)
        failure_reason = self.backend.failure_reason
        if failure_reason:
            # We attempted to authenticate but failed
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        elif not user:
            # We did not attempt to authenticate, let someone else try
            return None
        elif not user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))
        else:
            # authenticate should return a tuple of user and their token
            token = get_local_token(key)
            return (user, token)

    def authenticate_header(self, request):
        return self.request_auth_header