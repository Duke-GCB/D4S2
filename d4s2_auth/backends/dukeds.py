from .base import BaseBackend
from ddsc.core.ddsapi import DataServiceApi, DataServiceAuth
from ddsc.config import Config
from django.conf import settings
from requests.exceptions import HTTPError
from ..models import DukeDSAPIToken
from d4s2_api.models import DukeDSUser
from django.core.exceptions import ObjectDoesNotExist
import jwt


class DukeDSAuthBackend(BaseBackend):
    """
    Backend for DukeDS Auth
    Conveniently, the keys used by DukeDS user objects are a superset of the django ones,
    so we rely on the filtering in the base class
    """
    def __init__(self, save_tokens=True, save_dukeds_users=True):
        self.save_tokens = save_tokens
        self.save_dukeds_users = save_dukeds_users
        self.failure_reason = None

    @staticmethod
    def get_local_user(token):
        """
        Given a token, find a user that matches it
        :param token: An API token to search for in the local store
        :return: A DukeDSAPIToken object if one found, otherwise
        """
        try:
            local_token = DukeDSAuthBackend.get_local_token(token)
            return local_token.user
        except ObjectDoesNotExist as e:
            return None

    @staticmethod
    def get_local_token(token):
        return DukeDSAPIToken.objects.get(key=token)

    @staticmethod
    def check_jwt_token(token):
        """
        Uses PyJWT to parse and verify the token expiration
        :param token: A JWT token to check
        :return: The decoded token, or raises if invalid/expired
        """
        # jwt.decode will verify the expiration date of the token
        # We won't have the secret so we can't verify the signature, but we should verify everything else
        return jwt.decode(token, options={'verify_signature': False})

    @staticmethod
    def make_config(token):
        """
        Returns a DukeDS config object populated with URL and such
        from this application's django settings
        :param token: The authorization token for DukeDS
        :return: a ddsc.config.Config
        """
        config = Config()
        config.update_properties(settings.DDSCLIENT_PROPERTIES)
        config.values[Config.AUTH] = token
        return config

    def harmonize_user_details(self, details):
        """
        Overrides harmonize_user_details in BaseBackend to append @duke.edu to usernames from DukeDS
        :param details: incoming dictionary of user details
        :return: details harmonized for a django user object
        """
        details = super(DukeDSAuthBackend, self).harmonize_user_details(details)
        # For DukeDS, we need to append @duke.edu to username
        if 'username' in details:
            details['username'] = '{}@duke.edu'.format(details['username'])
        return details

    @staticmethod
    def save_dukeds_token(user, token):
        """
        Saves a DukeDSAPIToken object containing the provided token for the specified user
        Removes existing tokens for this user
        :param user: A django User
        :param token: the token text to save
        :return: The newly created token
        """
        # Delete any existing tokens for this user
        DukeDSAPIToken.objects.filter(user=user).delete()
        return DukeDSAPIToken.objects.create(user=user, key=token)

    @staticmethod
    def harmonize_dukeds_user_details(details):
        """
        Given a dict of
        :param details:
        :return:
        """
        mapping = dict((k, k) for k in ('full_name','email',))
        return BaseBackend.harmonize_dict(mapping,details)

    @staticmethod
    def save_dukeds_user(user, raw_user_dict):
        """
        :param user: A django model user
        :param raw_user_dict: user details from DukeDS API, including their id
        :return: The created or updated DukeDSUser object
        """
        user_dict = DukeDSAuthBackend.harmonize_dukeds_user_details(raw_user_dict)
        dukeds_user, created = DukeDSUser.objects.get_or_create(user=user,
                                                                dds_id=raw_user_dict.get('id'))
        if created:
            BaseBackend.update_model(dukeds_user, user_dict)
        return dukeds_user

    def authenticate(self, token):
        """
        Authenticate a user with a DukeDS API token. Returns None if no user could be authenticated,
        and sets the errors list with the reasons
        :param token: A JWT token
        :return: an authenticated, populated user if found, or None if not.
        """
        self.failure_reason = None
        # 1. check if token is valid for this purpose
        try:
            self.check_jwt_token(token)
        except jwt.InvalidTokenError as e:
            self.failure_reason = e
            # Token may be expired or may not be valid for this service, so return None
            return None

        # Token is a JWT and not expired
        # 2. Check if token exists in database
        user = self.get_local_user(token)
        if user:
            # token matched a user, return it
            return user

        # 3. Token appears valid but we have not seen it before.
        # Fetch user details from DukeDS

        config = self.make_config(token)
        auth = DataServiceAuth(config)
        api = DataServiceApi(auth, config.url)
        try:
            response = api.get_current_user()
            response.raise_for_status()
            user_dict = response.json()
        except HTTPError as e:
            self.failure_reason = e
            return None
        # DukeDS shouldn't stomp over existing user details
        user = self.save_user(user_dict, False)

        # 4. Have a user, save their token
        if self.save_tokens: self.save_dukeds_token(user, token)
        if self.save_dukeds_users: self.save_dukeds_user(user, user_dict)
        return user
