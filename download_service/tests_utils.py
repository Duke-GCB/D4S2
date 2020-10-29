from django.test.testcases import TestCase
from download_service.utils import make_client, CustomOAuthDataServiceAuth
from gcb_web_auth.models import DDSUserCredential, DDSEndpoint
from django.contrib.auth.models import User
from unittest.mock import patch, call, Mock


class MakeClientTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='client_user')
        self.endpoint = DDSEndpoint.objects.create(
            name='test',
            agent_key='agent-key',
            api_root='http://api.example.org/api/',
            portal_root='http://www.example.org/',
            openid_provider_service_id='abc-123',
            openid_provider_id='def-456',
            is_default=True
        )

    @patch('download_service.utils.get_dds_config_for_credentials')
    @patch('download_service.utils.Client')
    def test_makes_client_when_from_existing_dds_user_credential(self, mock_client, mock_get_dds_config_for_credentials):
        credential = DDSUserCredential.objects.create(user=self.user,
                                                      endpoint=self.endpoint,
                                                      token='SECRET-TOKEN',
                                                      dds_id='0000-1234')
        client = make_client(self.user)
        self.assertEqual(mock_get_dds_config_for_credentials.call_args, call(credential))
        self.assertEqual(mock_client.call_args, call(config=mock_get_dds_config_for_credentials.return_value))
        self.assertEqual(client, mock_client.return_value)

    @patch('download_service.utils.CustomOAuthDataServiceAuth')
    @patch('download_service.utils.get_dds_config_for_credentials')
    @patch('download_service.utils.get_oauth_token')
    @patch('download_service.utils.get_default_dds_endpoint')
    @patch('download_service.utils.Client')
    def test_makes_client_from_dds_token_when_no_dds_user_credential(self, mock_client, mock_get_default_dds_endpoint,
                                                                     mock_get_oauth_token,
                                                                     mock_get_dds_config_for_credentials,
                                                                     mock_custom_oauth_data_service_auth):
        mock_get_default_dds_endpoint.return_value = Mock(
            api_root='somehost',
            openid_provider_service_id='12345'
        )
        self.assertEqual(DDSUserCredential.objects.count(), 0)
        client = make_client(self.user)
        self.assertEqual(client, mock_client.return_value)
        client_config = mock_client.call_args.kwargs['config']
        self.assertEqual(client_config.url, 'somehost')
        create_data_service_auth = mock_client.call_args.kwargs['create_data_service_auth']
        data_service_auth = create_data_service_auth(None)
        self.assertEqual(data_service_auth, mock_custom_oauth_data_service_auth.return_value)
        mock_custom_oauth_data_service_auth.assert_called_with(self.user, '12345', None, set_status_msg=print)


class TestCustomOAuthDataServiceAuth(TestCase):
    def setUp(self):
        self.user = Mock()
        self.authentication_service_id = '1234'
        self.config = Mock()

    @patch('download_service.utils.get_oauth_token')
    def test_create_oauth_access_token(self, mock_get_oauth_token):
        mock_get_oauth_token.return_value.token_dict = {
            'access_token': '5678'
        }
        auth = CustomOAuthDataServiceAuth(self.user, self.authentication_service_id, self.config)
        token = auth.create_oauth_access_token()
        self.assertEqual(token, '5678')

    def test_get_authentication_service_id(self):
        auth = CustomOAuthDataServiceAuth(self.user, self.authentication_service_id, self.config)
        self.assertEqual(auth.get_authentication_service_id(), '1234')
