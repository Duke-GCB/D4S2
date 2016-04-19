import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from accept.views import MISSING_TOKEN_MSG, INVALID_TOKEN_MSG, TOKEN_NOT_FOUND_MSG
from handover_api.models import Handover
from mock import patch

def url_with_token(name, token=None):
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def create_handover_get_token():
    handover = Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')
    return str(handover.token)


class MockDDSUser(object):
    def __init__(self, full_name, email):
        self.full_name = full_name
        self.email = email


class MockDDSProject(object):
    def __init__(self, name):
        self.name = name
        self.children = []


def setup_mock_handover_details(MockHandoverDetails):
    x = MockHandoverDetails()
    x.get_from_user.return_value = MockDDSUser('joe', 'joe@joe.com')
    x.get_to_user.return_value = MockDDSUser('bob', 'bob@joe.com')
    x.get_project.return_value = MockDDSProject('project')


class AcceptTestCase(TestCase):
    def test_error_when_no_token(self):
        url = url_with_token('accept-index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TOKEN_MSG, str(response.content))

    @patch('accept.views.HandoverDetails')
    def test_normal_with_valid_token(self, MockHandoverDetails):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = url_with_token('accept-index', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))
        self.assertIn(token, str(response.content))

    def test_with_bad_token(self):
        token = create_handover_get_token() + "a"
        url = url_with_token('accept-index', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(INVALID_TOKEN_MSG, str(response.content))

    def test_with_token_not_found(self):
        token = str(uuid.uuid4())
        url = url_with_token('accept-index', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TOKEN_NOT_FOUND_MSG, str(response.content))


class ProcessTestCase(TestCase):
    def test_error_when_no_token(self):
        url = url_with_token('accept-process')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TOKEN_MSG, str(response.content))

    @patch('accept.views.HandoverDetails')
    @patch('accept.views.perform_handover')
    def test_normal_with_token_is_redirect(self, MockHandoverDetails, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = reverse('accept-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))

    def test_with_bad_token(self):
        token = create_handover_get_token() + "a"
        url = reverse('accept-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(INVALID_TOKEN_MSG, str(response.content))

    def test_with_token_not_found(self):
        token = str(uuid.uuid4())
        url = reverse('accept-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TOKEN_NOT_FOUND_MSG, str(response.content))

