from django.core.urlresolvers import reverse
from django.test import TestCase
from handover_api.models import DukeDSUser
from django.contrib.auth.models import User as django_user
from handover_api.auth import APIKeyTokenAuthentication
from rest_framework import status, exceptions
from rest_framework.test import APIClient, APIRequestFactory

class APIKeyTokenClientTestCase(TestCase):

    def setUp(self):
        user = django_user.objects.create_user('user1', is_staff=True)
        self.dsuser = DukeDSUser.objects.create(user=user,dds_id='abcd-1234-5678-efgh',api_key='secret-api-key')

    def test_header_auth(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + self.dsuser.api_key)
        url = reverse('handover-list')
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fails_badkey(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token prefix-' + self.dsuser.api_key)
        url = reverse('handover-list')
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fails_not_staff(self):
        user = django_user.objects.create_user('user2', is_staff=False)
        dsuser = DukeDSUser.objects.create(user=user,dds_id='abcd-1234-5678-0000',api_key='secret-api-key2')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ' + dsuser.api_key)
        url = reverse('handover-list')
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class APIKeyTokenAuthenticationTestCase(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.active_django_user = django_user.objects.create_user('active_user')
        self.active_ds_user = DukeDSUser.objects.create(user=self.active_django_user, dds_id='abcd-1234-5678-efgh', api_key='active-api-key')
        self.inactive_django_user = django_user.objects.create_user('inactive_user')
        self.inactive_django_user.is_active = False;
        self.inactive_django_user.save()
        self.inactive_ds_user = DukeDSUser.objects.create(user=self.inactive_django_user, dds_id='', api_key='inactive-api-key')
        self.url = reverse('handover-list')

    def test_no_token(self):
        request = self.factory.get(self.url)
        auth = APIKeyTokenAuthentication()
        self.assertIsNone(auth.authenticate(request), "if no token provided, no user should be returned")

    def test_valid_token(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token ' + self.active_ds_user.api_key
        auth = APIKeyTokenAuthentication()
        authenticated_user, token = auth.authenticate(request)
        self.assertEqual(self.active_django_user, authenticated_user)

    def test_invalid_token(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token abcada'
        auth = APIKeyTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)

    def test_inactive_user(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token ' + self.inactive_ds_user.api_key
        auth = APIKeyTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)

    def test_empty_key_cannot_auth(self):
        self.active_ds_user.api_key = ''
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token ' + self.active_ds_user.api_key
        auth = APIKeyTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)
