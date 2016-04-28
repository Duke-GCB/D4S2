import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TOKEN_MSG, INVALID_TOKEN_MSG, TOKEN_NOT_FOUND_MSG, REASON_REQUIRED_MSG
from handover_api.models import Handover, State
from mock import patch, Mock


def url_with_token(name, token=None):
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def create_handover():
    return Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')


def create_handover_get_token():
    handover = create_handover()
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
        url = url_with_token('ownership-prompt')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TOKEN_MSG, str(response.content))

    @patch('ownership.views.HandoverDetails')
    def test_normal_with_valid_token(self, MockHandoverDetails):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = url_with_token('ownership-prompt', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))
        self.assertIn(token, str(response.content))

    def test_with_bad_token(self):
        token = create_handover_get_token() + "a"
        url = url_with_token('ownership-prompt', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(INVALID_TOKEN_MSG, str(response.content))

    def test_with_token_not_found(self):
        token = str(uuid.uuid4())
        url = url_with_token('ownership-prompt', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TOKEN_NOT_FOUND_MSG, str(response.content))


class ProcessTestCase(TestCase):
    @patch('handover_api.utils.DDSUtil')
    def test_error_when_no_token(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        token = create_handover_get_token()
        url = url_with_token('ownership-process')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TOKEN_MSG, str(response.content))

    @patch('ownership.views.HandoverDetails')
    @patch('handover_api.utils.HandoverDetails')
    @patch('handover_api.utils.DDSUtil')
    def test_normal_with_token_is_redirect(self, MockHandoverDetails, MockHandoverDetails2, MockDDSUtil):
        setup_mock_handover_details(MockHandoverDetails)
        setup_mock_handover_details(MockHandoverDetails2)
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        token = create_handover_get_token()
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))

    def test_with_bad_token(self):
        token = create_handover_get_token() + "a"
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(INVALID_TOKEN_MSG, str(response.content))

    def test_with_token_not_found(self):
        token = str(uuid.uuid4())
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TOKEN_NOT_FOUND_MSG, str(response.content))

    def test_with_already_rejected(self):
        handover = create_handover()
        handover.mark_rejected('user', 'Done')
        token = handover.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.HANDOVER_CHOICES[State.REJECTED][1], str(response.content))

    def test_with_already_accepted(self):
        handover = create_handover()
        handover.mark_accepted('user')
        token = handover.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.HANDOVER_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_normal_with_reject(self, MockHandoverDetails, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token, 'reject':'reject'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reason for rejecting project', str(response.content))


class RejectReasonTestCase(TestCase):

    @patch('ownership.views.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_cancel_reject(self, MockHandoverDetails, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = reverse('ownership-reject')
        response = self.client.post(url, {'token': token, 'cancel': 'cancel'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_url = reverse('ownership-prompt')
        self.assertIn(expected_url, response.url)

    @patch('ownership.views.HandoverDetails')
    @patch('handover_api.utils.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_confirm_reject(self, MockHandoverDetails, MockHandoverDetails2, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        setup_mock_handover_details(MockHandoverDetails2)
        token = create_handover_get_token()
        url = reverse('ownership-reject')
        response = self.client.post(url, {'token': token, 'reject_reason':'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been rejected', str(response.content))

    @patch('ownership.views.HandoverDetails')
    @patch('handover_api.utils.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_reject_with_blank(self, MockHandoverDetails, MockHandoverDetails2, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        setup_mock_handover_details(MockHandoverDetails2)
        token = create_handover_get_token()
        url = reverse('ownership-reject')
        response = self.client.post(url, {'token': token, 'reject_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))
