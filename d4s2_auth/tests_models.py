import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test.testcases import TestCase

from .models import OAuthToken, OAuthService


class OAuthTokenTest(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(username='user1')
        self.service = OAuthService.objects.create(name='service1',
                                                   client_id='id123',
                                                   client_secret='secret456',
                                                   redirect_uri='https://redirect/',
                                                   scope='scope1',
                                                   authorization_uri='https://authorize/',
                                                   token_uri='https://token/')
        self.token_dict = {'token': 'abc123'}
        self.token_json = json.dumps(self.token_dict)

    def test_token_types(self):
        self.assertEqual(type(self.token_dict), dict, 'token dict is dict')
        self.assertEqual(type(self.token_json), str, 'token json is string')

    def test_create_token(self):
        t = OAuthToken.objects.create(user=self.user, service=self.service, token_json=self.token_json)
        self.assertEqual(t.user, self.user, 'sets user')
        self.assertEqual(t.service, self.service, 'sets service')
        self.assertEqual(t.token_json, self.token_json, 'sets json')

    def test_requires_unique_user_service(self):
        OAuthToken.objects.create(user=self.user, service=self.service, token_json=self.token_json)
        with self.assertRaises(IntegrityError):
            OAuthToken.objects.create(user=self.user, service=self.service, token_json='{}')

    def test_requires_unique_service_token(self):
        OAuthToken.objects.create(user=self.user, service=self.service, token_json=self.token_json)
        user2 = get_user_model().objects.create(username='user2')
        with self.assertRaises(IntegrityError):
            OAuthToken.objects.create(user=user2, service=self.service, token_json=self.token_json)

    def test_allows_duplicate_user_token(self):
        # User and token may be the same if service is different
        t1 = OAuthToken.objects.create(user=self.user, service=self.service, token_json=self.token_json)
        service2 = OAuthService.objects.create(name='service2',
                                               client_id='id456',
                                               client_secret='secret222',
                                               redirect_uri='https://redirect2/',
                                               scope='scope2',
                                               authorization_uri='https://authorize2/',
                                               token_uri='https://token2/')
        t2 = OAuthToken.objects.create(user=self.user, service=service2, token_json=self.token_json)
        self.assertNotEqual(t1.service, t2.service, 'Services are unique')
        self.assertEqual(t1.user, t2.user, 'Users are identical')
        self.assertEqual(t1.token_json, t2.token_json, 'Token jsons are identical')

    def test_deserialize_json(self):
        t = OAuthToken.objects.create(user=self.user, service=self.service, token_json=self.token_json)
        self.assertEqual(t.token_dict, self.token_dict, 'De-serializes JSON from string')

    def test_serialize_json(self):
        t = OAuthToken.objects.create(user=self.user, service=self.service)
        t.token_dict = self.token_dict
        t.save()
        self.assertEqual(t.token_json, self.token_json)



