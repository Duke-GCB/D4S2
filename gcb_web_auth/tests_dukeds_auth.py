from django.contrib.auth.models import User as django_user
from django.core.urlresolvers import reverse
from django.test import TestCase
from rest_framework import status, exceptions
from rest_framework.test import APIClient, APIRequestFactory, APITestCase
from d4s2_api.models import DukeDSUser
from gcb_web_auth.dukeds_auth import DukeDSTokenAuthentication
from gcb_web_auth.models import DukeDSAPIToken
from mock.mock import patch, Mock


class ResponseStatusCodeTestCase(object):
    def assertUnauthorized(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                         'Got {}, expected 401 when authentication fails'
                         .format(response.status_code))

    def assertForbidden(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                         'Got {}, expected 403 when additional access required'
                         .format(response.status_code))


class DukeDSTokenAuthenticationClientTestCase(APITestCase, ResponseStatusCodeTestCase):

    def setUp(self):
        self.user = django_user.objects.create_user('user1', is_staff=True)

    def set_request_token(self, key):
        # This is how we set headers in the testing client.
        # They must be transformed to the internal format (HTTP_X_DUKEDS_AUTHORIZATION)
        # Because the test client won't transform from X-DukeDS-Authorization
        headers = {DukeDSTokenAuthentication().internal_request_auth_header(): key}
        self.client.credentials(**headers)

    @patch('gcb_web_auth.backends.dukeds.decode')
    def test_header_auth(self, mock_jwt_decode):
        token = DukeDSAPIToken.objects.create(user=self.user, key='2mma0c3')
        self.set_request_token(token.key)
        url = reverse('delivery-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_jwt_decode.called_with(token.key))

    def test_fails_badkey(self):
        DukeDSAPIToken.objects.create(user=self.user, key='2mma0c3')
        self.set_request_token('abacaa') # Not a valid JWT
        url = reverse('delivery-list')
        response = self.client.get(url)
        self.assertUnauthorized(response)


class DukeDSTokenAuthenticationTestCase(TestCase):

    def patch_backend(self):
        patcher = patch('gcb_web_auth.dukeds_auth.DukeDSAuthBackend')
        mock_backend_cls = patcher.start()
        mock_backend = Mock()
        mock_backend_cls.return_value = mock_backend
        mock_authenticate = Mock()
        mock_backend.authenticate = mock_authenticate
        mock_backend.failure_reason = None
        self.mock_backend = mock_backend
        self.mock_authenticate = mock_authenticate
        self.addCleanup(patcher.stop)

    def setUp(self):
        self.patch_backend()
        factory = APIRequestFactory()
        self.url = reverse('delivery-list')
        self.request = factory.get(self.url)
        self.active_django_user = django_user.objects.create_user('active_user')
        self.active_token = DukeDSAPIToken.objects.create(user=self.active_django_user, key='active_token')
        self.active_ds_user = DukeDSUser.objects.create(user=self.active_django_user, dds_id='abcd-1234-5678-efgh')
        self.inactive_django_user = django_user.objects.create_user('inactive_user')
        self.inactive_django_user.is_active = False;
        self.inactive_django_user.save()
        self.inactive_ds_user = DukeDSUser.objects.create(user=self.inactive_django_user, dds_id='')
        self.inactive_token = DukeDSAPIToken.objects.create(user=self.inactive_django_user, key='inactive_token')
        self.auth = DukeDSTokenAuthentication()

    def authenticate(self):
        return self.auth.authenticate(self.request)

    def set_auth_header(self, value):
        # This is how we set headers in the testing client.
        # They must be transformed to the internal format (HTTP_X_DUKEDS_AUTHORIZATION)
        # Because the test client won't transform from X-DukeDS-Authorization
        self.request.META[self.auth.internal_request_auth_header()] = value

    def test_no_token(self):
        self.set_auth_header('')
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.authenticate()

    def test_valid_token(self):
        self.mock_authenticate.return_value = self.active_django_user
        self.set_auth_header('active_token')
        authenticated_user, token = self.authenticate()
        self.assertEqual(self.active_django_user, authenticated_user)

    def test_invalid_token(self):
        self.set_auth_header('invalid token')
        self.mock_backend.failure_reason = 'Invalid Token'

        with self.assertRaises(exceptions.AuthenticationFailed):
            self.authenticate()

    def test_inactive_user(self):
        self.mock_authenticate.return_value = self.inactive_django_user
        self.set_auth_header('inactive_token')
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.authenticate()

    def test_empty_key_cannot_auth(self):
        self.set_auth_header('')
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.authenticate()
