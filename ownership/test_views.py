import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TOKEN_MSG, INVALID_TOKEN_MSG, TOKEN_NOT_FOUND_MSG, REASON_REQUIRED_MSG
from d4s2_api.models import Delivery, State, DukeDSProject, DukeDSUser
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from django.contrib.auth.models import User as django_user
from mock import patch, Mock


def url_with_token(name, token=None):
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def create_delivery():
    project1 = DukeDSProject.objects.create(project_id='project1')
    fromuser1 = DukeDSUser.objects.create(dds_id='fromuser1')
    touser1= DukeDSUser.objects.create(dds_id='touser1')
    return Delivery.objects.create(project=project1, from_user=fromuser1, to_user=touser1)


def create_delivery_get_token():
    delivery = create_delivery()
    return str(delivery.token)


def setup_mock_delivery_details(MockDeliveryDetails):
    x = MockDeliveryDetails()
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

    @patch('ownership.views.DeliveryDetails')
    def test_normal_with_valid_token(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        token = create_delivery_get_token()
        url = url_with_token('ownership-prompt', token)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))
        self.assertIn(token, str(response.content))

    def test_with_bad_token(self):
        token = create_delivery_get_token() + "a"
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

    @patch('d4s2_api.utils.DDSUtil')
    def test_error_when_no_token(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        token = create_delivery_get_token()
        url = url_with_token('ownership-process', token)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TOKEN_MSG, str(response.content))

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DeliveryDetails')
    @patch('d4s2_api.utils.DDSUtil')
    def test_normal_with_token_is_redirect(self, MockDeliveryDetails, MockDeliveryDetails2, MockDDSUtil):
        setup_mock_delivery_details(MockDeliveryDetails)
        setup_mock_delivery_details(MockDeliveryDetails2)
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        token = create_delivery_get_token()
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertNotIn(MISSING_TOKEN_MSG, str(response.content))

    def test_with_bad_token(self):
        token = create_delivery_get_token() + "a"
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
        delivery = create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        token = delivery.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))

    def test_with_already_accepted(self):
        delivery = create_delivery()
        delivery.mark_accepted('user', 'email text')
        token = delivery.token
        url = reverse('ownership-process')
        response = self.client.post(url, {'token': token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.DeliveryDetails')
    @patch('ownership.views.perform_delivery')
    def test_normal_with_decline(self, MockDeliveryDetails, mock_perform_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        token = create_delivery_get_token()
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

    @patch('ownership.views.DeliveryDetails')
    @patch('ownership.views.perform_delivery')
    def test_cancel_decline(self, MockDeliveryDetails, mock_perform_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        token = create_delivery_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'cancel': 'cancel'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_url = reverse('ownership-prompt')
        self.assertIn(expected_url, response.url)

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DeliveryDetails')
    @patch('ownership.views.perform_delivery')
    def test_confirm_decline(self, MockDeliveryDetails, MockDeliveryDetails2, mock_perform_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        setup_mock_delivery_details(MockDeliveryDetails2)
        token = create_delivery_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'decline_reason':'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been declined', str(response.content))

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DeliveryDetails')
    @patch('ownership.views.perform_delivery')
    def test_decline_with_blank(self, MockDeliveryDetails, MockDeliveryDetails2, mock_perform_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        setup_mock_delivery_details(MockDeliveryDetails2)
        token = create_delivery_get_token()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'token': token, 'decline_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))
