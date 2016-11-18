from django.test import TestCase
from .models import OAuthService
from mock.mock import patch


class OAuthViewsTest(TestCase):
    def setUp(self):
        # Create a service
        self.service = OAuthService.objects.create(client_id='id123',
                                                   client_secret='secret456',
                                                   redirect_uri='https://redirect/',
                                                   scope='scope1',
                                                   authorization_uri='https://authorize/',
                                                   token_uri='https://token/')

    def test_redirects_to_authorize(self):
        response = self.client.get('/auth/authorize/', follow=False)
        self.assertEqual(response.status_code, 302, 'Should redirect')
        self.assertIn('https://authorize/', response.get('Location'), 'Should redirect to authorization_uri')

    @patch('d4s2_auth.views.get_resource')
    @patch('d4s2_auth.views.get_token_dict')
    def test_authorize_callback(self, mock_get_token_dict, mock_get_resource):
        token_dict = {'access_token': 'foo-bar'}
        mock_get_token_dict.return_value = token_dict
        mock_get_resource.return_value = {'eppn': 'netid'}
        response = self.client.get('/auth/code/')
        self.assertTrue(mock_get_token_dict.called)
        self.assertTrue(mock_get_resource.called_with(self.service, token_dict))
        self.assertContains(response, 'Welcome netid')
