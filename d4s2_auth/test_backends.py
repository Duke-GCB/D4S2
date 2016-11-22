from django.test import TestCase
from mock.mock import patch, MagicMock, Mock
from .backends import OAuth2Backend, USERNAME_KEY
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
