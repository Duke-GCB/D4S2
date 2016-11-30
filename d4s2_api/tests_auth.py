from django.contrib.auth.models import User as django_user
from django.core.urlresolvers import reverse
from django.test import TestCase
from rest_framework import status, exceptions
from rest_framework.test import APIClient, APIRequestFactory

from d4s2_api.auth import DukeDSTokenAuthentication
from d4s2_api.models import DukeDSUser


class ResponseStatusCodeTestCase(object):
    def assertUnauthorized(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                         'TokenAuthentication got {}, expected 401 when authentication fails'
                         .format(response.status_code))

    def assertForbidden(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                         'TokenAuthentication got {}, expected 403 when additional access required'
                         .format(response.status_code))


# TODO: Update these tests after writing DukeDSToken
class DukeDSTokenAuthenticationClientTestCase(TestCase, ResponseStatusCodeTestCase):

    def setUp(self):
        user = django_user.objects.create_user('user1', is_staff=True)
        self.dsuser = DukeDSUser.objects.create(user=user, dds_id='abcd-1234-5678-efgh')

    def test_header_auth(self):
        client = APIClient()
        raise Exception('TODO: get a token')
        client.credentials(HTTP_AUTHORIZATION='Token ')
        url = reverse('delivery-list')
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fails_badkey(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token bad-bad-bad')
        url = reverse('delivery-list')
        response = client.get(url)
        self.assertUnauthorized(response)

    def test_fails_not_staff(self):
        user = django_user.objects.create_user('user2', is_staff=False)
        dsuser = DukeDSUser.objects.create(user=user, dds_id='abcd-1234-5678-0000')
        raise Exception('TODO: get a valid token')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token ')
        url = reverse('delivery-list')
        response = client.get(url)
        self.assertForbidden(response)


class DukeDSTokenAuthenticationTestCase(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.active_django_user = django_user.objects.create_user('active_user')
        self.active_ds_user = DukeDSUser.objects.create(user=self.active_django_user, dds_id='abcd-1234-5678-efgh')
        self.inactive_django_user = django_user.objects.create_user('inactive_user')
        self.inactive_django_user.is_active = False;
        self.inactive_django_user.save()
        self.inactive_ds_user = DukeDSUser.objects.create(user=self.inactive_django_user, dds_id='')
        self.url = reverse('delivery-list')

    def test_no_token(self):
        request = self.factory.get(self.url)
        auth = DukeDSTokenAuthentication()
        self.assertIsNone(auth.authenticate(request), "if no token provided, no user should be returned")

    def test_valid_token(self):
        request = self.factory.get(self.url)
        raise Exception('TODO: get a token')
        request.META['HTTP_AUTHORIZATION'] = 'Token '
        auth = DukeDSTokenAuthentication()
        authenticated_user, token = auth.authenticate(request)
        self.assertEqual(self.active_django_user, authenticated_user)

    def test_invalid_token(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token abcada'
        auth = DukeDSTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)

    def test_inactive_user(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token '
        auth = DukeDSTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)

    def test_empty_key_cannot_auth(self):
        request = self.factory.get(self.url)
        request.META['HTTP_AUTHORIZATION'] = 'Token '
        auth = DukeDSTokenAuthentication()
        with self.assertRaises(exceptions.AuthenticationFailed):
            auth.authenticate(request)

# Additional tests
# looks up for existing DukeDS Token and uses (does not fetch new)
# Checks expiration of token and fetches new if needed
# fetches new token if none present
