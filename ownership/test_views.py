import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TOKEN_MSG, INVALID_TOKEN_MSG, TOKEN_NOT_FOUND_MSG, REASON_REQUIRED_MSG
from handover_api.models import Delivery, State, DukeDSProject, DukeDSUser
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from django.contrib.auth.models import User as django_user
from mock import patch, Mock


def url_with_token(name, token=None):
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def create_handover():
    project1 = DukeDSProject.objects.create(project_id='project1')
    fromuser1 = DukeDSUser.objects.create(dds_id='fromuser1')
    touser1= DukeDSUser.objects.create(dds_id='touser1')
    return Delivery.objects.create(project=project1, from_user=fromuser1, to_user=touser1)


def create_handover_get_token():
    handover = create_handover()
    return str(handover.token)


def setup_mock_handover_details(MockHandoverDetails):
    x = MockHandoverDetails()
    x.get_from_user.return_value = MockDDSUser('joe', 'joe@joe.com')
    x.get_to_user.return_value = MockDDSUser('bob', 'bob@joe.com')
    x.get_project.return_value = MockDDSProject('project')
    x.get_action_template_text.return_value = ('Subject Template {{ project_name }}', 'Body Template {{ recipient_name }}')


class AuthenticatedTestCase(TestCase):
    def setUp(self):
        username = 'ownership_user'
        password = 'secret'
        django_user.objects.create_user(username, password=password)
        self.client.login(username=username, password=password)


class AcceptTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = url_with_token('ownership-prompt', 'token-data')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

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


class ProcessTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': 'token-data'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('handover_api.utils.DDSUtil')
    def test_error_when_no_token(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        token = create_handover_get_token()
        url = url_with_token('ownership-process', token)
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

    def test_with_already_declined(self):
        handover = create_handover()
        handover.mark_declined('user', 'Done', 'email text')
        token = handover.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))

    def test_with_already_accepted(self):
        handover = create_handover()
        handover.mark_accepted('user', 'email text')
        token = handover.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_normal_with_decline(self, MockHandoverDetails, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token, 'decline':'decline'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reason for declining project', str(response.content))


class DeclineReasonTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-decline')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('ownership.views.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_cancel_decline(self, MockHandoverDetails, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        token = create_handover_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'cancel': 'cancel'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_url = reverse('ownership-prompt')
        self.assertIn(expected_url, response.url)

    @patch('ownership.views.HandoverDetails')
    @patch('handover_api.utils.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_confirm_decline(self, MockHandoverDetails, MockHandoverDetails2, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        setup_mock_handover_details(MockHandoverDetails2)
        token = create_handover_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'decline_reason':'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been declined', str(response.content))

    @patch('ownership.views.HandoverDetails')
    @patch('handover_api.utils.HandoverDetails')
    @patch('ownership.views.perform_handover')
    def test_decline_with_blank(self, MockHandoverDetails, MockHandoverDetails2, mock_perform_handover):
        setup_mock_handover_details(MockHandoverDetails)
        setup_mock_handover_details(MockHandoverDetails2)
        token = create_handover_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'decline_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))
