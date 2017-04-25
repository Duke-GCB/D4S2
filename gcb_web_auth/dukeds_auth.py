from rest_framework import authentication
from rest_framework import exceptions
from django.utils.translation import ugettext_lazy as _
from .backends.dukeds import get_local_token, DukeDSAuthBackend


class DukeDSTokenAuthentication(authentication.BaseAuthentication):

    """
    DukeDS api_token authentication, verifying the token with the DukeDS get_current_user endpoint

    Clients should authenticate by passing the token key in the "X_DukeDS_Authorization" HTTP header

    For example:

        X-DukeDS-Authorization: abcd.ef123.4567

        Can change the expected header, should probably do that
    """
    request_auth_header = 'X-DukeDS-Authorization'

    def internal_request_auth_header(self):
        """
        Transforms the header that clients will specify into the META key
        that the server here will see. Header fields are prefixed with 'HTTP_',
        uppercased, and '-' is replaced with '_'
        :return:
        """
        return 'HTTP_{}'.format(self.request_auth_header.replace('-','_').upper())

    def __init__(self):
        self.backend = DukeDSAuthBackend()

    def authenticate(self, request):
        if self.internal_request_auth_header() not in request.META:
            # Our header is not present, don't try to authenticate
            return None
        token = request.META.get(self.internal_request_auth_header())
        if not token:
            msg = _('Invalid token header. No credentials provided.')
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
