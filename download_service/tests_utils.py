from django.test.testcases import TestCase
from download_service.utils import make_client
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

    @patch('download_service.utils.get_dds_token')
    @patch('download_service.utils.make_auth_config')
    @patch('download_service.utils.Client')
    def test_makes_client_from_dds_token_when_no_dds_user_credential(self, mock_client, mock_make_auth_config, mock_get_dds_token):
        self.assertEqual(DDSUserCredential.objects.count(), 0)
        mock_key = Mock()
        mock_get_dds_token.return_value.key = mock_key
        client = make_client(self.user)
        self.assertEqual(mock_get_dds_token.call_args, call(self.user))
        self.assertEqual(mock_make_auth_config.call_args, call(mock_key))
        self.assertEqual(mock_client.call_args, call(config=mock_make_auth_config.return_value))
        self.assertEqual(client, mock_client.return_value)


