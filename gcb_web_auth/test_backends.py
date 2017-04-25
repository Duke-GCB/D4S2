from django.test import TestCase
from mock.mock import patch, MagicMock, Mock

from .backends import OAuth2Backend, DukeDSAuthBackend
from .backends.dukeds import remove_invalid_dukeds_tokens
from .backends.base import BaseBackend
from .tests_oauth_utils import make_oauth_service
from django.contrib.auth import get_user_model
from .models import DukeDSAPIToken, DukeDSSettings
from jwt import InvalidTokenError


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

    @patch('gcb_web_auth.backends.oauth.user_details_from_token')
    def tests_authenticate(self, mock_user_details_from_token):
        username = 'user123'
        mock_user_details_from_token.return_value = {self.username_key: username}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token': 'foo-bar-baz'}
        user = self.oauth_backend.authenticate(service, token_dict)
        self.assertTrue(mock_user_details_from_token.called, 'should call to get user details')
        self.assertIsNotNone(user, 'Should have user')
        self.assertEqual(user.username, username)

    @patch('gcb_web_auth.backends.oauth.user_details_from_token')
    def tests_authenticate_failure(self, mock_user_details_from_token):
        mock_user_details_from_token.return_value = {}
        service = make_oauth_service(MagicMock)
        token_dict = {'access_token', 'foo-bar-baz'}
        user = self.oauth_backend.authenticate(service, token_dict)
        self.assertTrue(mock_user_details_from_token.called, 'shouild call to get user details')
        self.assertIsNone(user, 'should not authenticate a user with no details')

    def tests_harmonize_user_details(self):
        mapped = self.oauth_backend.harmonize_user_details(self.details)
        self.assertEqual(set(mapped.keys()), set(self.oauth_backend.get_user_details_map().keys()), 'Maps user details to only safe keys')
        self.assertEqual(mapped.get('username'), self.details.get('sub'), 'Maps username from sub')

    @patch('gcb_web_auth.backends.oauth.user_details_from_token')
    def tests_update_user(self, mock_user_details_from_token):
        mock_user_details_from_token.return_value = self.details
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


class DukeDSAuthBackendTestCase(TestCase):

    def setUp(self):
        # Patch the jwt decode function everwherywhere
        jwt_decode_patcher = patch('gcb_web_auth.backends.dukeds.decode')
        self.mock_jwt_decode = jwt_decode_patcher.start()
        self.addCleanup(jwt_decode_patcher.stop)

        # Mock the data service api and auth
        dataservice_api_patcher = patch('gcb_web_auth.backends.dukeds.DataServiceApi')
        dataservice_auth_patcher = patch('gcb_web_auth.backends.dukeds.DataServiceAuth')
        self.mock_dataservice_api = dataservice_api_patcher.start()
        self.mock_dataservice_auth = dataservice_auth_patcher.start()
        self.addCleanup(dataservice_api_patcher.stop)
        self.addCleanup(dataservice_auth_patcher.stop)

        self.dukeds_backend = DukeDSAuthBackend()
        user_model = get_user_model()
        self.user = user_model.objects.create(username='user@host.com')
        self.key = 'abcd123'
        self.token = DukeDSAPIToken.objects.create(key=self.key, user=self.user)

        self.details = {
            'id': 'A481707B-F93E-4941-A441-12BF9316C1D9',
            'username': 'ab1756',
            'first_name': 'Aaron',
            'last_name': 'Burr',
            'email': 'aaron.burr@duke.edu',
        }

    def test_uses_local_without_calling_dukeds(self):
        authenticated_user = self.dukeds_backend.authenticate(self.key)
        self.assertEqual(authenticated_user, self.user, 'Authenticate should return the user matching the token')
        self.assertFalse(self.mock_dataservice_api.called, 'Should not instantiate a dataservice API when token already exists')
        self.assertFalse(self.mock_dataservice_auth.called, 'Should not instantiate a dataservice auth when token already exists')

    def test_calls_dukeds_for_unrecognized_token(self):
        key = 'unrecognized'
        DukeDSSettings.objects.create(url='', portal_root='', openid_provider_id='')
        self.assertEqual(DukeDSAPIToken.objects.filter(key=key).count(), 0, 'Should not have a token with this key')
        mock_get_current_user = MagicMock(return_value=MagicMock(json=MagicMock(return_value=self.details)))
        self.mock_dataservice_api.return_value.get_current_user = mock_get_current_user
        authenticated_user = self.dukeds_backend.authenticate(key)
        self.assertEqual(authenticated_user.username, self.details['username'] + '@duke.edu', msg='Should populate username and append @duke.edu')
        self.assertEqual(authenticated_user.email, self.details['email'], 'Should populate email')
        self.assertEqual(authenticated_user.dukedsuser.dds_id, self.details['id'], 'Should create a dukeds user and populate it with id')
        self.assertEqual(authenticated_user.first_name, self.details['first_name'], 'Should populate first name')
        self.assertEqual(authenticated_user.last_name, self.details['last_name'], 'Should populate last name')
        self.assertTrue(mock_get_current_user.called, 'Should call get_current_user to get user details')

    def test_fails_bad_token(self):
        error = InvalidTokenError()
        self.mock_jwt_decode.side_effect = error
        authenticated_user = self.dukeds_backend.authenticate(self.key)
        self.assertIsNone(authenticated_user, 'Should not authenticate user with bad token')
        self.assertTrue(self.mock_jwt_decode.called, 'Should call jwt decode')
        self.assertEqual(self.dukeds_backend.failure_reason, error, 'should fail because of our invalid token error')

    def test_removes_invalid_tokens(self):
        error = InvalidTokenError()
        self.mock_jwt_decode.side_effect = error
        self.assertEqual(DukeDSAPIToken.objects.count(), 1, 'Should have one token in database')
        remove_invalid_dukeds_tokens(self.user)
        self.assertTrue(self.mock_jwt_decode.called, 'Should call jwt decode')
        self.assertEqual(DukeDSAPIToken.objects.count(), 0, 'Should have removed token')


class BaseBackendTestCase(TestCase):

    def tests_update_user_flag(self):
        details = {
            'username': 'ab123',
            'first_name': 'Aaron',
            'last_name': 'Burr',
            'email': 'ab123@us.gov'
        }

        user_model = get_user_model()
        user = user_model.objects.create(username=details.get('username'))
        self.assertEqual(user.first_name, '', 'User created should not have first_name')

        backend = BaseBackend()
        saved_user = backend.save_user(details, update=False)
        self.assertEqual(saved_user.first_name, '', 'should not have updated user')

        saved_user = backend.save_user(details, update=True)
        self.assertEqual(saved_user.first_name, 'Aaron', 'should have updated user')
