from django.test import TestCase
from mock.mock import patch, MagicMock, Mock
from django.contrib.auth import get_user_model
from .oauth_utils import *
from django.contrib.auth.models import User


def make_oauth_service(cls=MagicMock, save=False):
    """
    Helper method that can make a mock service with the parameters
    or a full database-backed object if the OAuthService class is passed
    :param cls: Class to instantiate
    :param save: If true, call save() on the service afer creating
    :return: a mocked object or database backed (ready for save())
    """
    service = cls(client_id='id123',
                  client_secret='secret456',
                  redirect_uri='redirect',
                  scope='scope1',
                  authorization_uri='authorize',
                  token_uri='token')
    if save: service.save()
    return service


def configure_mock_session(mock_session):
    mock_authorization_url = Mock()
    mock_authorization_url.return_value = 'authorization_url'
    mock_session.return_value.authorization_url = mock_authorization_url
    mock_fetch_token = Mock()
    mock_fetch_token.return_value = {'access_token':'abcxyz'}
    mock_session.return_value.fetch_token = mock_fetch_token


def configure_mock_client(mock_client, response_json={'key':'value'}):
    # requests.post() -> obj w/ .json()
    mock_post = Mock()
    mock_response = Mock()
    mock_post.return_value = mock_response
    mock_response.json = Mock()
    mock_response.json.return_value = response_json
    mock_client.post = mock_post


# Create your tests here.
class OAuthUtilsTest(TestCase):

    def setUp(self):
        self.service = make_oauth_service(cls=MagicMock)

    @patch('gcb_web_auth.oauth_utils.OAuth2Session')
    def test_make_oauth(self, mock_session):
        oauth = make_oauth_session(self.service)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')
        self.assertIsNotNone(oauth, 'Returns an OAuth session')

    @patch('gcb_web_auth.oauth_utils.OAuth2Session')
    def test_authorization_url(self, mock_session):
        configure_mock_session(mock_session)
        auth_url = authorization_url(self.service)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')
        self.assertTrue(mock_session.mock_authorization_url.called_with('authorize'), 'calls authorize url with expected data')
        self.assertEqual(auth_url, 'authorization_url', 'returned authorization url is expected')

    @patch('gcb_web_auth.oauth_utils.OAuth2Session')
    def test_get_token_dict(self, mock_session):
        configure_mock_session(mock_session)
        mock_response = Mock()
        token = get_token_dict(self.service, mock_response)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')
        self.assertTrue(mock_session.mock_fetch_token.called_with
                        (self.service.token_uri, authorization_response=mock_response, client_secret=self.service.client_secret),
                        'Fetches token with expected arguments')
        self.assertEqual(token, {'access_token': 'abcxyz'}, 'Returns expected token')

    @patch('gcb_web_auth.oauth_utils.make_oauth_session')
    def test_user_details_from_token(self, mock_make_oauth_session):
        mock_client = Mock()
        mock_make_oauth_session.return_value = mock_client
        user_details = {'name':'George Washington'}
        configure_mock_client(mock_client, user_details)
        token_dict = {'access_token': 'abcxyz'}
        resource = user_details_from_token(self.service, token_dict)
        self.assertEqual(resource, user_details, 'Returns expected resource')
        self.assertTrue(mock_make_oauth_session.post.called_with(self.service.resource_uri), 'Posts to resource URI')

    @patch('gcb_web_auth.oauth_utils.revoke_token')
    def test_updates_existing_token_and_revokes(self, mock_revoke_token):
        service = make_oauth_service(OAuthService, save=True)
        user = get_user_model().objects.create(username='user123')
        token_dict1 = {'access_token': 'aaaaa1'}
        token_dict2 = {'access_token': 'bbbbb2'}
        t1 = save_token(service, token_dict1, user)
        t1_id, t1_token = t1.id, t1.token_dict
        t2 = save_token(service, token_dict2, user)
        t2_id, t2_token = t2.id, t2.token_dict
        self.assertEqual(t1_id, t2_id, 'Token should be updated with same id')
        self.assertNotEqual(t1_token, t2_token, 'Token data have been updated')
        self.assertTrue(mock_revoke_token.called_with(t1), 'Should have revoked t1')
        self.assertEqual(mock_revoke_token.call_count, 1, 'Should revoke once')

    @patch('gcb_web_auth.oauth_utils.requests')
    def test_revoke_token(self, mock_client):
        configure_mock_client(mock_client)
        service = make_oauth_service(OAuthService, save=True)
        user = get_user_model().objects.create(username='user123')
        token = OAuthToken.objects.create(user=user, service=service)
        token.token_dict = {'access_token': 'aaaaa1'}
        token.save()
        revoke_token(token) # Will raise exception if not passed correct data
        self.assertTrue(mock_client.post.called_with(self.service.revoke_uri), 'Posts to revoke URI')

    @patch('gcb_web_auth.oauth_utils.revoke_token')
    def test_no_revoke_token_on_save_new(self, mock_revoke_token):
        service = make_oauth_service(OAuthService, save=True)
        user = get_user_model().objects.create(username='user123')
        token_dict = {'access_token': 'aaaaa1'}
        t1 = save_token(service, token_dict, user)
        self.assertFalse(mock_revoke_token.called, 'Should not revoke token')
        self.assertEqual(t1.token_dict, token_dict, 'Should return saved token')


class OAuthTokenUtilTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'
        self.token = DukeDSAPIToken.objects.create(user=self.user, key='some-token')
        self.oauth_service = OAuthService.objects.create(name="Test Service")
        DukeDSSettings.objects.create(url='', portal_root='', openid_provider_id='')

    @patch('gcb_web_auth.oauth_utils.check_jwt_token')
    def gcb_web_auth(self, mock_check_jwt_token):
        mock_check_jwt_token.return_value = True
        local_token = get_local_dds_token(self.user)
        self.assertEqual(local_token.key, 'some-token', 'Should return token when check passes')

    @patch('gcb_web_auth.oauth_utils.check_jwt_token')
    def test_no_local_token_when_check_fails(self, mock_check_jwt_token):
        mock_check_jwt_token.return_value = False
        local_token = get_local_dds_token(self.user)
        self.assertIsNone(local_token, 'Should return none when check fails')

    @patch('gcb_web_auth.oauth_utils.requests')
    def test_gets_dds_token_from_oauth(self, mock_requests):
        mocked_dds_token = {'api_token': 'abc1234'}
        mock_response = Mock(raise_for_status=Mock(), json=Mock(return_value=mocked_dds_token))
        mock_requests.get = Mock(return_value=mock_response)
        oauth_token = OAuthToken.objects.create(user=self.user,
                                                service=self.oauth_service,
                                                token_json='{"access_token":"g2jo83lmvasijgq"}')
        exchanged = get_dds_token_from_oauth(oauth_token)
        # Should parse the JSON of the oauth_token and send the value of access_token to the DDS API
        sent_get_params = mock_requests.get.call_args[1].get('params')
        self.assertEqual(sent_get_params['access_token'], 'g2jo83lmvasijgq')
        self.assertTrue(mock_requests.get.called)
        self.assertTrue(mock_response.raise_for_status.called)
        self.assertEqual(exchanged, mocked_dds_token)

    @patch('gcb_web_auth.oauth_utils.requests')
    def test_handles_dds_token_from_oauth_failure(self, mock_requests):
        mock_requests.HTTPError = Exception
        mocked_dds_token = {'api_token': 'abc1234'}
        raise_for_status = Mock()
        raise_for_status.side_effect = mock_requests.HTTPError()
        mock_response = Mock(raise_for_status=raise_for_status)
        mock_requests.get = Mock(return_value=mock_response)
        oauth_token = OAuthToken.objects.create(user=self.user,
                                                service=self.oauth_service,
                                                token_json='{"access_token":"g2jo83lmvasijgq"}')
        with self.assertRaises(NoTokenException):
            get_dds_token_from_oauth(oauth_token)
