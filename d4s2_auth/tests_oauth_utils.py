from django.test import TestCase
from mock.mock import patch, MagicMock, Mock

from .oauth_utils import *


def make_oauth_service(cls=MagicMock):
    """
    Helper method that can make a mock service with the parameters
    or a full database-backed object if the OAuthService class is passed
    :param cls: Class to instantiate
    :return: a mocked object or database backed (ready for save())
    """
    return cls(client_id='id123',
                     client_secret='secret456',
                     redirect_uri='redirect',
                     scope='scope1',
                     authorization_uri='authorize',
                     token_uri='token')


def configure_mock_session(mock_session):
    mock_authorization_url = Mock()
    mock_authorization_url.return_value = 'authorization_url'
    mock_session.return_value.authorization_url = mock_authorization_url
    mock_fetch_token = Mock()
    mock_fetch_token.return_value = {'access_token':'abcxyz'}
    mock_session.return_value.fetch_token = mock_fetch_token


def configure_mock_requests(mock_requests):
    # requests.post() -> obj w/ .json()
    mock_post = Mock()
    mock_response = Mock()
    mock_post.return_value= mock_response
    mock_response.json = Mock()
    mock_response.json.return_value = {'key':'value'}
    mock_requests.post = mock_post


# Create your tests here.
class OAuthUtilsTest(TestCase):

    def setUp(self):
        self.service = make_oauth_service(cls=MagicMock)

    @patch('d4s2_auth.oauth_utils.OAuth2Session')
    def test_make_oauth(self, mock_session):
        oauth = make_oauth(self.service)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')

    @patch('d4s2_auth.oauth_utils.OAuth2Session')
    def test_authorization_url(self, mock_session):
        configure_mock_session(mock_session)
        auth_url = authorization_url(self.service)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')
        self.assertTrue(mock_session.mock_authorization_url.called_with('authorize'), 'calls authorize url with expected data')
        self.assertEqual(auth_url, 'authorization_url', 'returned authorization url is expected')

    @patch('d4s2_auth.oauth_utils.OAuth2Session')
    def test_get_token_dict(self, mock_session):
        configure_mock_session(mock_session)
        mock_response = Mock()
        token = get_token_dict(self.service, mock_response)
        self.assertTrue(mock_session.called, 'instantiates an oauth session')
        self.assertTrue(mock_session.mock_fetch_token.called_with
                        (self.service.token_uri, authorization_response=mock_response, client_secret=self.service.client_secret),
                        'Fetches token with expected arguments')
        self.assertEqual(token, {'access_token': 'abcxyz'}, 'Returns expected token')

    @patch('d4s2_auth.oauth_utils.requests')
    def test_get_user_details(self, mock_requests):
        configure_mock_requests(mock_requests)
        token_dict = {'access_token': 'abcxyz'}
        resource = get_user_details(self.service, token_dict)
        self.assertEqual(resource, {'key':'value'}, 'Returns expected resource')
        self.assertTrue(mock_requests.post.called_with(self.service.resource_uri, token_dict), 'Posts to resource URI with token')

    def test_updates_existing_token(self):
        service = make_oauth_service(OAuthService)
        service.save()
        user = get_user_model().objects.create(username='user123')
        token_dict1 = {'access_token': 'aaaaa1'}
        token_dict2 = {'access_token': 'bbbbb2'}
        t1 = save_token(service, token_dict1, user)
        t1_id, t1_token = t1.id, t1.token_dict
        t2 = save_token(service, token_dict2, user)
        t2_id, t2_token = t2.id, t2.token_dict
        self.assertEqual(t1_id, t2_id, 'Token should be updated with same id')
        self.assertNotEqual(t1_token, t2_token, 'Token data have been updated')
