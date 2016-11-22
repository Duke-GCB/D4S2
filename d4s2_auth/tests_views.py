from django.test import TestCase
from .models import OAuthService
from mock.mock import patch
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse

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
        self.client.logout()
        response = self.client.get(reverse('authorize'), follow=False)
        self.assertEqual(response.status_code, 302, 'Should redirect')
        self.assertIn('https://authorize/', response.get('Location'), 'Should redirect to authorization_uri')

    @patch('d4s2_auth.views.pop_state')
    @patch('d4s2_auth.views.save_token')
    @patch('d4s2_auth.views.get_token_dict')
    @patch('d4s2_auth.views.authenticate')
    @patch('d4s2_auth.views.login')
    def test_authorize_callback(self, mock_login, mock_authenticate, mock_get_token_dict, mock_save_token, mock_pop_state):
        token_dict = {'access_token': 'foo-bar'}
        user = get_user_model().objects.create(username='USER')
        mock_get_token_dict.return_value = token_dict
        mock_authenticate.return_value = user
        mock_pop_state.return_value = ''
        response = self.client.get(reverse('callback'))
        self.assertTrue(mock_get_token_dict.called, 'Get token dict called')
        self.assertTrue(mock_authenticate.called_with(self.service, token_dict), 'authenticate called')
        self.assertTrue(mock_pop_state.called, 'Should attempt to lookup the state')
        self.assertTrue(mock_save_token.called_with(self.service, token_dict), 'Save token called')
        self.assertTrue(mock_login.called, 'Login called')
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False,
                             msg_prefix='Should redirect to home after authorize success')

    @patch('d4s2_auth.views.pop_state')
    @patch('d4s2_auth.views.save_token')
    @patch('d4s2_auth.views.get_token_dict')
    @patch('d4s2_auth.views.authenticate')
    @patch('d4s2_auth.views.login')
    def test_authorize_fails_bad_authenticate(self, mock_login, mock_authenticate, mock_get_token_dict, mock_save_token, mock_pop_state):
        token_dict = {'access_token': 'foo-bar'}
        mock_get_token_dict.return_value = token_dict
        mock_authenticate.return_value = None
        response = self.client.get(reverse('callback'))
        self.assertTrue(mock_get_token_dict.called, 'Get token dict called')
        self.assertTrue(mock_authenticate.called_with(self.service, token_dict), 'authenticate called')
        self.assertTrue(mock_pop_state.called, 'Should attempt to lookup the state')
        self.assertFalse(mock_login.called, 'Login should not be called when no user')
        self.assertFalse(mock_save_token.called, 'save token should not be called when no user returned')
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False,
                             msg_prefix='Should redirect to login after authorize failure')

    def test_login_page(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Login', msg_prefix='Login page should be reachable while logged out')

    def test_home_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, '/accounts/login/?next=/auth/home/', fetch_redirect_response=False,
                             msg_prefix='Should redirect to login when accessing home while logged out')