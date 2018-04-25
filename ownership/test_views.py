import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TRANSFER_ID_MSG, TRANSFER_ID_NOT_FOUND, REASON_REQUIRED_MSG, SHARE_IN_RESPONSE_TO_DELIVERY_MSG
from ownership.views import DDSDeliveryType, S3DeliveryType
from d4s2_api.models import DDSDelivery, S3Delivery, State, ShareRole
from switchboard.mocks_ddsutil import MockDDSUser
from django.contrib.auth.models import User as django_user
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
from mock import patch, Mock, call


def url_with_transfer_id(name, transfer_id=None):
    url = reverse(name)
    if transfer_id:
        url = "{}?transfer_id={}".format(url, transfer_id)
    return url


def create_delivery():
    return DDSDelivery.objects.create(project_id='project1', from_user_id='fromuser1',
                                      to_user_id='touser1', transfer_id='abc123')


def create_delivery_get_transfer_id():
    delivery = create_delivery()
    return str(delivery.transfer_id)


def setup_mock_delivery_details(MockDeliveryDetails):
    x = MockDeliveryDetails()
    x.get_from_user.return_value = MockDDSUser('joe', 'joe@joe.com')
    x.get_to_user.return_value = MockDDSUser('bob', 'bob@joe.com')
    x.get_action_template_text.return_value = ('Action Subject Template {{ project_name }}',
                                               'Action Body Template {{ recipient_name }}, Action User Message {{ user_message }}')
    x.get_share_template_text.return_value = ('Share Subject Template {{ project_name }}',
                                               'Share Body Template {{ recipient_name }}, Share User Message {{ user_message }}')
    x.get_email_context.return_value = {
            'project_name': 'project',
            'recipient_name': 'bob',
            'recipient_email': 'bob@joe.com',
            'sender_email': 'joe@joe.com',
            'sender_name': 'joe',
            'project_url': 'http://example.com/project-url',
            'accept_url': '',
            'type': 'accept',
            'message': '',
            'user_message': 'msg',
            'warning_message': '',
        }
    x.get_context.return_value = {'transfer_id':'abc123'}
    return x


def setup_mock_delivery_type(mock_get_delivery_type):
    mock_delivery_type = mock_get_delivery_type.return_value
    mock_delivery_type.name = 'mock'
    mock_delivery_type.delivery_cls = DDSDelivery
    mock_delivery_type.make_delivery_details.return_value = setup_mock_delivery_details(Mock())
    # Convenience for tests to assign return values without .return_value.return_value
    mock_delivery_type.mock_delivery_details = mock_delivery_type.make_delivery_details.return_value
    mock_delivery_type.mock_delivery_util = mock_delivery_type.make_delivery_util.return_value
    mock_delivery_type.mock_processed_message = mock_delivery_type.make_processed_message.return_value
    return mock_delivery_type

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

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_valid_transfer_id(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
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

    def test_error_when_no_transfer_id(self):
        transfer_id = create_delivery_get_transfer_id()
        url = url_with_transfer_id('ownership-process')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TRANSFER_ID_MSG, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_transfer_id_is_redirect(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        mock_delivery_type.mock_delivery_util.get_warning_message.return_value = 'Failed to share with Joe, Tom'
        mock_delivery_type.mock_processed_message.email_text = 'email text'
        delivery = create_delivery()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        expected_warning_message = urlencode({'transfer_id': transfer_id, 'warning_message': 'Failed to share with Joe, Tom', 'delivery_type': 'mock'})
        expected_url = reverse('ownership-accepted') + '?' + expected_warning_message
        self.assertRedirects(response, expected_url)
        self.assertNotIn(MISSING_TRANSFER_ID_MSG, str(response.content))
        self.assertTrue(mock_delivery_type.mock_delivery_util.accept_project_transfer.called)
        self.assertTrue(mock_delivery_type.mock_delivery_util.share_with_additional_users.called)
        self.assertTrue(mock_delivery_type.make_processed_message.called)
        self.assertTrue(mock_delivery_type.mock_processed_message.send.called)

    def test_with_bad_transfer_id(self):
        transfer_id = create_delivery_get_transfer_id() + "a"
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TRANSFER_ID_NOT_FOUND, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_accept_with_already_declined(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_accept_with_already_accepted(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = create_delivery()
        delivery.mark_accepted('user', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': delivery.transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_decline(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline':'decline'}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reason for declining delivery', str(response.content))


class DeclineReasonTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-decline')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_cancel_decline(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = create_delivery_get_transfer_id()
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'cancel': 'cancel'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        expected_url = reverse('ownership-prompt')
        self.assertIn(expected_url, response.url)
        self.assertFalse(mock_delivery_type.mock_delivery_util.accept_project_transfer.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_confirm_decline(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        mock_delivery_type.mock_processed_message.email_text = 'email text'
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason':'Wrong person.'}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been declined', str(response.content))
        self.assertTrue(mock_delivery_type.mock_delivery_util.decline_delivery.called)
        self.assertTrue(mock_delivery_type.make_processed_message.called)
        self.assertTrue(mock_delivery_type.mock_processed_message.send.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_decline_with_blank(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_decline_with_already_declined(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': 'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_decline_with_already_accepted(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = create_delivery()
        delivery.mark_accepted('user','email type')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': 'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))


class AcceptedPageTestCase(AuthenticatedTestCase):

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_renders_accepted_page_with_project_url(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-accepted')
        response = self.client.get(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('View this data', str(response.content))

    def test_renders_error_with_bad_transfer_id(self):
        url = reverse('ownership-accepted')
        response = self.client.get(url, {'transfer_id': 'garbage'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DDSDeliveryTypeTestCase(TestCase):

    def setUp(self):
        self.delivery_type = DDSDeliveryType()

    def test_name_and_delivery_cls(self):
        self.assertEqual(self.delivery_type.name, 'dds')
        self.assertEqual(self.delivery_type.delivery_cls, DDSDelivery)

    @patch('ownership.views.DeliveryDetails')
    def test_makes_dds_delivery_details(self, mock_delivery_details):
        details = self.delivery_type.make_delivery_details('arg1','arg2')
        mock_delivery_details.assert_called_once_with('arg1', 'arg2')
        self.assertEqual(details, mock_delivery_details.return_value)

    @patch('ownership.views.DeliveryUtil')
    def test_makes_dds_delivery_util(self, mock_delivery_util):
        util = self.delivery_type.make_delivery_util('arg1','arg2')
        mock_delivery_util.assert_called_once_with('arg1', 'arg2', share_role=ShareRole.DOWNLOAD, share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        self.assertEqual(util, mock_delivery_util.return_value)

    @patch('ownership.views.ProcessedMessage')
    def test_makes_dds_processed_message(self, mock_processed_message):
        message = self.delivery_type.make_processed_message('arg1', arg2='arg2')
        mock_processed_message.assert_called_once_with('arg1', arg2='arg2')
        self.assertEqual(message, mock_processed_message.return_value)


class S3DeliveryTypeTestCase(TestCase):

    def setUp(self):
        self.delivery_type = S3DeliveryType()

    def test_name_and_delivery_cls(self):
        self.assertEqual(self.delivery_type.name, 's3')
        self.assertEqual(self.delivery_type.delivery_cls, S3Delivery)

    @patch('ownership.views.S3DeliveryDetails')
    def test_makes_dds_delivery_details(self, mock_delivery_details):
        details = self.delivery_type.make_delivery_details('arg1','arg2')
        mock_delivery_details.assert_called_once_with('arg1', 'arg2')
        self.assertEqual(details, mock_delivery_details.return_value)

    @patch('ownership.views.S3DeliveryUtil')
    def test_makes_dds_delivery_util(self, mock_delivery_util):
        util = self.delivery_type.make_delivery_util('arg1','arg2')
        mock_delivery_util.assert_called_once_with('arg1', 'arg2')
        self.assertEqual(util, mock_delivery_util.return_value)

    @patch('ownership.views.S3ProcessedMessage')
    def test_makes_dds_processed_message(self, mock_processed_message):
        message = self.delivery_type.make_processed_message('arg1', arg2='arg2')
        mock_processed_message.assert_called_once_with('arg1', arg2='arg2')
        self.assertEqual(message, mock_processed_message.return_value)
