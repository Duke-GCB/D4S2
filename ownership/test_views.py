import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TRANSFER_ID_MSG, INVALID_TRANSFER_ID, TRANSFER_ID_NOT_FOUND, REASON_REQUIRED_MSG
from d4s2_api.models import Delivery, State, DukeDSProject, DukeDSUser
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from django.contrib.auth.models import User as django_user
from mock import patch, Mock


def url_with_transfer_id(name, transfer_id=None):
    url = reverse(name)
    if transfer_id:
        url = "{}?transfer_id={}".format(url, transfer_id)
    return url


def create_delivery():
    project1 = DukeDSProject.objects.create(project_id='project1')
    fromuser1 = DukeDSUser.objects.create(dds_id='fromuser1')
    touser1= DukeDSUser.objects.create(dds_id='touser1')
    return Delivery.objects.create(project=project1, from_user=fromuser1, to_user=touser1, transfer_id='abc123')


def create_delivery_get_transfer_id():
    delivery = create_delivery()
    return str(delivery.transfer_id)


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
        url = url_with_transfer_id('ownership-prompt', 'transfer-id')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    def test_error_when_no_transfer_id(self):
        url = url_with_transfer_id('ownership-prompt')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TRANSFER_ID_MSG, str(response.content))

    @patch('ownership.views.DeliveryDetails')
    def test_normal_with_valid_transfer_id(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        transfer_id = create_delivery_get_transfer_id()
        url = url_with_transfer_id('ownership-prompt', transfer_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(MISSING_TRANSFER_ID_MSG, str(response.content))
        self.assertIn(transfer_id, str(response.content))

    def test_with_transfer_id_not_found(self):
        transfer_id = str(uuid.uuid4())
        url = url_with_transfer_id('ownership-prompt', transfer_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TRANSFER_ID_NOT_FOUND, str(response.content))


class ProcessTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': 'transfer-id'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('d4s2_api.utils.DDSUtil')
    def test_error_when_no_transfer_id(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        transfer_id = create_delivery_get_transfer_id()
        url = url_with_transfer_id('ownership-process', transfer_id)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TRANSFER_ID_MSG, str(response.content))

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DDSUtil')
    @patch('ownership.views.accept_delivery')
    @patch('ownership.views.ProcessedMessage')
    def test_normal_with_transfer_id_is_redirect(self, mock_processed_message, mock_accept_delivery, mock_dds_util, mock_delivery_details):
        setup_mock_delivery_details(mock_delivery_details)
        mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value.is_complete.return_value = False
        mock_ddsutil = mock_dds_util()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        transfer_id = create_delivery_get_transfer_id()
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertNotIn(MISSING_TRANSFER_ID_MSG, str(response.content))
        self.assertTrue(mock_accept_delivery.called)
        self.assertTrue(mock_processed_message.called)
        self.assertTrue(mock_processed_message.return_value.send.called)

    def test_with_bad_transfer_id(self):
        transfer_id = create_delivery_get_transfer_id() + "a"
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TRANSFER_ID_NOT_FOUND, str(response.content))

    @patch('ownership.views.DeliveryDetails')
    def test_with_already_declined(self, mock_delivery_details):
        setup_mock_delivery_details(mock_delivery_details)
        delivery = create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))

    @patch('ownership.views.DeliveryDetails')
    def test_with_already_accepted(self, mock_delivery_details):
        setup_mock_delivery_details(mock_delivery_details)
        delivery = create_delivery()
        delivery.mark_accepted('user', 'email text')
        mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': delivery.transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.DeliveryDetails')
    def test_normal_with_decline(self, mock_delivery_details):
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = Delivery.objects.get(transfer_id=transfer_id)
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline':'decline'})
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
    @patch('ownership.views.accept_delivery')
    def test_cancel_decline(self, MockDeliveryDetails, mock_accept_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        transfer_id = create_delivery_get_transfer_id()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'cancel': 'cancel'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_url = reverse('ownership-prompt')
        self.assertIn(expected_url, response.url)
        self.assertFalse(mock_accept_delivery.called)

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DeliveryDetails')
    @patch('ownership.views.decline_delivery')
    # TODO: Fix order
    def test_confirm_decline(self, MockDeliveryDetails, MockDeliveryDetails2, mock_decline_delivery):
        setup_mock_delivery_details(MockDeliveryDetails)
        setup_mock_delivery_details(MockDeliveryDetails2)
        transfer_id = create_delivery_get_transfer_id()
        url = reverse('ownership-decline')
        # THIS SHOULD FAIL UNLESS 'DECLINE'
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason':'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been declined', str(response.content))
        self.assertTrue(mock_decline_delivery.called)

    @patch('ownership.views.DeliveryDetails')
    @patch('d4s2_api.utils.DeliveryDetails')
    def test_decline_with_blank(self, MockDeliveryDetails, MockDeliveryDetails2):
        setup_mock_delivery_details(MockDeliveryDetails)
        setup_mock_delivery_details(MockDeliveryDetails2)
        transfer_id = create_delivery_get_transfer_id()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))
