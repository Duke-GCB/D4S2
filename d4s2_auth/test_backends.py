from django.test import TestCase
from mock.mock import patch, MagicMock

from .backends import OAuth2Backend, DukeDSAuthBackend
from .tests_oauth_utils import make_oauth_service
from django.contrib.auth import get_user_model

class OAuth2BackendTestCase(TestCase):

    def setUp(self):
        self.oauth_backend = OAuth2Backend()
        self.username_key = 'sub'
        self.details = {
            'dukeNetID': 'ab1756',
            'dukeUniqueID': '01234567',
            'email': 'aaron.burr@duke.edu',
            'email_verified': False,
            'family_name': 'Burr',
            'given_name': 'Aaron',
            'name': 'Aaron Burr',
            'sub': 'ab1756@duke.edu'
        }

    @patch('d4s2_auth.backends.oauth.get_user_details')
    def tests_authenticate(self, mock_get_user_details):
        username = 'user123'
        mock_get_user_details.return_value = {self.username_key: username}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token', 'foo-bar-baz'}
        user = self.oauth_backend.authenticate(service, token_dict)
        self.assertTrue(mock_get_user_details.called, 'shouild call to get user details')
        self.assertIsNotNone(user, 'Should have user')
        self.assertEqual(user.username, username)

    @patch('d4s2_auth.backends.oauth.get_user_details')
    def tests_authenticate_failure(self, mock_get_user_details):
        mock_get_user_details.return_value = {}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token', 'foo-bar-baz'}
        user = self.oauth_backend.authenticate(service, token_dict)
        self.assertTrue(mock_get_user_details.called, 'shouild call to get user details')
        self.assertIsNone(user, 'should not authenticate a user with no details')

    def tests_map_user_details(self):
        mapped = self.oauth_backend.map_user_details(self.details)
        self.assertEqual(set(mapped.keys()), set(self.oauth_backend.get_user_details_map().keys()), 'Maps user details to only safe keys')
        self.assertEqual(mapped.get('username'), self.details.get('sub'), 'Maps username from sub')

    @patch('d4s2_auth.backends.oauth.get_user_details')
    def tests_update_user(self, mock_get_user_details):
        mock_get_user_details.return_value = self.details
        user_model = get_user_model()
        user = user_model.objects.create(username=self.details.get('sub'))
        orig_user_pk = user.pk
        self.assertEqual(len(user.first_name), 0, 'User first name should be blank initially')
        self.assertEqual(len(user.email), 0, 'User email should be blank initially')
        service = make_oauth_service(MagicMock)
        user = self.oauth_backend.authenticate(service, None)
        self.assertIsNotNone(user, 'Should return authenticated user')
        user = user_model.objects.get(pk=orig_user_pk)
        self.assertIsNotNone(user, 'Should restore user')
        self.assertEqual(user.pk, orig_user_pk, 'Should update existing user')
        self.assertEqual(user.first_name, self.details.get('given_name'), 'Updates first name')
        self.assertEqual(user.email, self.details.get('email'), 'Updates email')

# TODO: Test the DukeDSBackend and BaseBackend too
# TODO: Test the update flag and decide how to use it

class DukeDSBackendTestCase(TestCase):

    def setUp(self):
        self.dukeds_backend = DukeDSAuthBackend()
