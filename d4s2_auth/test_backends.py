from django.test import TestCase
from mock.mock import patch, MagicMock

from .backends import OAuth2Backend, USERNAME_KEY, USER_DETAILS_MAP
from .tests_oauth_utils import make_oauth_service


class OAuth2BackendTestCase(TestCase):

    def setUp(self):
        self.backend = OAuth2Backend()

    @patch('d4s2_auth.backends.get_user_details')
    def tests_authenticate(self, mock_get_user_details):
        username = 'user123'
        mock_get_user_details.return_value = {USERNAME_KEY: username}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token', 'foo-bar-baz'}
        user = self.backend.authenticate(service, token_dict)
        self.assertTrue(mock_get_user_details.called, 'shouild call to get user details')
        self.assertIsNotNone(user, 'Should have user')
        self.assertEqual(user.username, username)

    @patch('d4s2_auth.backends.get_user_details')
    def tests_authenticate_failure(self, mock_get_user_details):
        mock_get_user_details.return_value = {}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token', 'foo-bar-baz'}
        user = self.backend.authenticate(service, token_dict)
        self.assertTrue(mock_get_user_details.called, 'shouild call to get user details')
        self.assertIsNone(user, 'should not authenticate a user with no details')

    def tests_map_user_details(self):
        details = {
            'dukeNetID': 'ab1756',
            'dukeUniqueID': '01234567',
            'email': 'aaron.burr@duke.edu',
            'email_verified': False,
            'family_name': 'Burr',
            'given_name': 'Aaron',
            'name': 'Aaron Burr',
            'sub': 'ab1756@duke.edu'
        }
        mapped = OAuth2Backend.map_user_details(details)
        self.assertEqual(set(mapped.keys()), set(USER_DETAILS_MAP.keys()), 'Maps user details to only safe keys')
        self.assertEqual(mapped.get('username'), 'ab1756@duke.edu', 'Maps username from sub')
