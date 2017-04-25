from django.test import TestCase
from .models import OAuthService, OAuthState
from mock.mock import patch
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from .views import push_state, pop_state, StateException
from django.test.client import RequestFactory


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
        response = self.client.get(reverse('auth-authorize'), follow=False)
        self.assertEqual(response.status_code, 302, 'Should redirect')
        self.assertIn('https://authorize/', response.get('Location'), 'Should redirect to authorization_uri')

    @patch('gcb_web_auth.views.pop_state')
    @patch('gcb_web_auth.views.save_token')
    @patch('gcb_web_auth.views.get_token_dict')
    @patch('gcb_web_auth.views.authenticate')
    @patch('gcb_web_auth.views.login')
    def test_authorize_callback(self, mock_login, mock_authenticate, mock_get_token_dict, mock_save_token, mock_pop_state):
        token_dict = {'access_token': 'foo-bar'}
        user = get_user_model().objects.create(username='USER')
        mock_get_token_dict.return_value = token_dict
        mock_authenticate.return_value = user
        mock_pop_state.return_value = ''
        response = self.client.get(reverse('auth-callback'))
        self.assertTrue(mock_get_token_dict.called, 'Get token dict called')
        self.assertTrue(mock_authenticate.called_with(self.service, token_dict), 'authenticate called')
        self.assertTrue(mock_pop_state.called, 'Should attempt to lookup the state')
        self.assertTrue(mock_save_token.called_with(self.service, token_dict), 'Save token called')
        self.assertTrue(mock_login.called, 'Login called')
        self.assertRedirects(response, reverse('auth-home'), fetch_redirect_response=False,
                             msg_prefix='Should redirect to home after authorize success')

    @patch('gcb_web_auth.views.pop_state')
    @patch('gcb_web_auth.views.save_token')
    @patch('gcb_web_auth.views.get_token_dict')
    @patch('gcb_web_auth.views.authenticate')
    @patch('gcb_web_auth.views.login')
    def test_authorize_fails_bad_authenticate(self, mock_login, mock_authenticate, mock_get_token_dict, mock_save_token, mock_pop_state):
        token_dict = {'access_token': 'foo-bar'}
        mock_get_token_dict.return_value = token_dict
        mock_authenticate.return_value = None
        response = self.client.get(reverse('auth-callback'))
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
        response = self.client.get(reverse('auth-home'))
        self.assertRedirects(response, '/accounts/login/?next=/auth/home/', fetch_redirect_response=False,
                             msg_prefix='Should redirect to login when accessing home while logged out')

    def test_redirects_unconfigured(self):
        self.service.delete()
        self.assertEqual(OAuthService.objects.count(), 0)
        response = self.client.get(reverse('auth-authorize'))
        self.assertRedirects(response, reverse('auth-unconfigured'), fetch_redirect_response=False,
                             msg_prefix='Should redirect to unconfigured page when no oauth services present')

    def test_unconfigured(self):
        response = self.client.get(reverse('auth-unconfigured'))
        self.assertContains(response, 'Error', msg_prefix='Should render unconfigured page with Error text')


class OAuthStateViewsTestCase(TestCase):

    def setUp(self):
        self.request_factory = RequestFactory()

    def test_push_state(self):
        state_string = 'state123'
        destination = '/next/path'
        request = self.request_factory.get('/',data={'next':destination})
        state = push_state(request, state_string)
        self.assertEqual(state.destination, destination, 'saved state should include destination')

    def test_push_state_raises_witout_state(self):
        request = self.request_factory.get('/',data={'next':'blah'})
        with self.assertRaises(StateException):
            push_state(request, None) # Should raise if state is empty

    def test_pop_state(self):
        state_string = 'state456'
        destination = '/protected-resource'
        OAuthState.objects.create(state=state_string, destination=destination)
        self.assertEqual(OAuthState.objects.count(), 1, 'One state should exist')
        request = self.request_factory.get('/', data={'state': state_string})
        popped_destination = pop_state(request)
        self.assertEqual(destination, popped_destination, 'Restored state should return destination')
        self.assertEqual(OAuthState.objects.count(), 0, 'State should be deleted')

    def test_pop_state_raises_without_state(self):
        destination = '/next/path'
        request = self.request_factory.get('/',data={'next':destination}) # a request without a state param
        with self.assertRaises(StateException):
            pop_state(request) # Should raise an exception when no state in the request
