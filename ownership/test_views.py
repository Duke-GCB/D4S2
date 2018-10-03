import uuid
from django.core.urlresolvers import reverse
from rest_framework import status
from django.test.testcases import TestCase
from ownership.views import MISSING_TRANSFER_ID_MSG, TRANSFER_ID_NOT_FOUND, REASON_REQUIRED_MSG, NOT_RECIPIENT_MSG
from switchboard.dds_util import SHARE_IN_RESPONSE_TO_DELIVERY_MSG
from ownership.views import DDSDeliveryType, S3DeliveryType, S3NotRecipientException
from d4s2_api.models import DDSDelivery, S3Delivery, State, ShareRole, EmailTemplateSet, UserEmailTemplateSet, \
    EmailTemplate, EmailTemplateType
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
        self.user = django_user.objects.create_user(username, password=password)
        self.client.login(username=username, password=password)
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        self.user_email_template_set = UserEmailTemplateSet.objects.create(user=self.user, email_template_set=self.email_template_set)

    def create_delivery(self):
        return DDSDelivery.objects.create(project_id='project1', from_user_id='fromuser1',
                                          to_user_id='touser1', transfer_id='abc123',
                                          email_template_set=self.email_template_set)

    def create_delivery_get_transfer_id(self):
        delivery = self.create_delivery()
        return str(delivery.transfer_id)


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
        transfer_id = self.create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = url_with_transfer_id('ownership-prompt', transfer_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(MISSING_TRANSFER_ID_MSG, str(response.content))
        self.assertIn(transfer_id, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_not_recipient_exception(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = self.create_delivery_get_transfer_id()
        url = url_with_transfer_id('ownership-prompt', transfer_id)
        mock_get_delivery_type.return_value.make_delivery_details.side_effect = S3NotRecipientException()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(NOT_RECIPIENT_MSG, str(response.content))

    def test_with_transfer_id_not_found(self):
        transfer_id = str(uuid.uuid4())
        url = url_with_transfer_id('ownership-prompt', transfer_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TRANSFER_ID_NOT_FOUND, str(response.content))

    def test_post_not_allowed(self):
        url = url_with_transfer_id('ownership-prompt')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ProcessTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': 'transfer-id'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    def test_error_when_no_transfer_id(self):
        transfer_id = self.create_delivery_get_transfer_id()
        url = url_with_transfer_id('ownership-process')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(MISSING_TRANSFER_ID_MSG, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_transfer_id_is_redirect(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        mock_delivery_type.transfer_delivery.return_value = 'Failed to share with Joe, Tom'
        mock_delivery_type.mock_processed_message.email_text = 'email text'
        delivery = self.create_delivery()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        expected_warning_message = urlencode({'transfer_id': transfer_id, 'warning_message': 'Failed to share with Joe, Tom', 'delivery_type': 'mock'})
        expected_url = reverse('ownership-accepted') + '?' + expected_warning_message
        self.assertRedirects(response, expected_url)
        self.assertNotIn(MISSING_TRANSFER_ID_MSG, str(response.content))
        self.assertTrue(mock_delivery_type.transfer_delivery.called)

    def test_with_bad_transfer_id(self):
        transfer_id = self.create_delivery_get_transfer_id() + "a"
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(TRANSFER_ID_NOT_FOUND, str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_accept_with_already_declined(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.accept_project_transfer.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_accept_with_already_accepted(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_accepted('user', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': delivery.transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.accept_project_transfer.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_normal_with_decline(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = self.create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline':'decline'}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reason for declining delivery', str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.accept_project_transfer.called)

    def test_get_not_allowed(self):
        url = url_with_transfer_id('ownership-process')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('switchboard.dds_util.DDSUtil')
    @patch('d4s2_api.utils.Message')
    def test_receiving_user_can_accept_deliveries_without_email_template_set(self, mock_message, mock_dds_util):
        mock_message.return_value.email_text = ''

        # accepting/current user should have not email template setup
        self.user_email_template_set.delete()

        # a template set is specified when the delivery was created
        sending_user = django_user.objects.create_user('sender', password='senderpass')
        sender_email_template_set = EmailTemplateSet.objects.create(name='group1')
        EmailTemplate.objects.create(template_set=sender_email_template_set,
                                     owner=sending_user,
                                     template_type=EmailTemplateType.objects.get(name='accepted'),
                                     subject='Subject',
                                     body='email body')
        delivery = DDSDelivery.objects.create(
            project_id='project1', from_user_id='fromuser1',
            to_user_id='touser1', transfer_id='abc123',
            email_template_set=sender_email_template_set)
        transfer_id = delivery.transfer_id

        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        delivery.refresh_from_db()
        self.assertEqual(delivery.state, State.ACCEPTED)

    @patch('switchboard.dds_util.DDSUtil')
    @patch('d4s2_api.utils.Message')
    def test_delivery_emails_always_use_senders_email_template_set(self, mock_message, mock_dds_util):
        mock_message.return_value.email_text = ''

        # a template set is specified when the delivery was created
        sending_user = django_user.objects.create_user('sender', password='senderpass')
        sender_email_template_set = EmailTemplateSet.objects.create(name='group1')
        sender_template = EmailTemplate.objects.create(template_set=sender_email_template_set,
                                                       owner=sending_user,
                                                       template_type=EmailTemplateType.objects.get(name='accepted'),
                                                       subject='Subject',
                                                       body='email body')
        delivery = DDSDelivery.objects.create(
            project_id='project1', from_user_id='fromuser1',
            to_user_id='touser1', transfer_id='abc123',
            email_template_set=sender_email_template_set)
        transfer_id = delivery.transfer_id

        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': transfer_id}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # check that the sender template subject/body was used to render the email
        args, kwargs = mock_message.call_args
        from_email, to_email, subject, body, context = args
        self.assertEqual(subject, sender_template.subject)
        self.assertEqual(body, sender_template.body)

class DeclineGetTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-decline')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_get_with_already_accepted(self,mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_accepted('user', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        url = reverse('ownership-decline')
        response = self.client.get(url, {'transfer_id': delivery.transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_get_with_already_declined(self,mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        url = reverse('ownership-decline')
        response = self.client.get(url, {'transfer_id': delivery.transfer_id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))


class DeclinePostTestCase(AuthenticatedTestCase):

    def test_redirects_for_login(self):
        self.client.logout()
        url = reverse('ownership-decline')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('login', response['Location'])

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_cancel_decline(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = self.create_delivery_get_transfer_id()
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
        transfer_id = self.create_delivery_get_transfer_id()
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
        transfer_id = self.create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(REASON_REQUIRED_MSG, str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.decline_delivery.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_decline_with_already_declined(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_declined('user', 'Done', 'email text')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': 'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.DECLINED][1], str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.decline_delivery.called)

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_decline_with_already_accepted(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        delivery = self.create_delivery()
        delivery.mark_accepted('user','email type')
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = delivery
        transfer_id = delivery.transfer_id
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': transfer_id, 'decline_reason': 'Wrong person.'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(State.DELIVERY_CHOICES[State.ACCEPTED][1], str(response.content))
        self.assertFalse(mock_delivery_type.mock_delivery_util.decline_delivery.called)


class AcceptedPageTestCase(AuthenticatedTestCase):

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_renders_accepted_page_with_project_url(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = self.create_delivery_get_transfer_id()
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

    def test_post_not_allowed(self):
        url = url_with_transfer_id('ownership-accepted')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class DeclinedPageTestCase(AuthenticatedTestCase):

    @patch('ownership.views.DeliveryViewBase.get_delivery_type')
    def test_renders_declined_page_with_project_url(self, mock_get_delivery_type):
        mock_delivery_type = setup_mock_delivery_type(mock_get_delivery_type)
        transfer_id = self.create_delivery_get_transfer_id()
        mock_delivery_type.mock_delivery_details.from_transfer_id.return_value.get_delivery.return_value = DDSDelivery.objects.get(
            transfer_id=transfer_id)
        url = reverse('ownership-declined')
        response = self.client.get(url, {'transfer_id': transfer_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('has been declined', str(response.content))

    def test_renders_error_with_bad_transfer_id(self):
        url = reverse('ownership-declined')
        response = self.client.get(url, {'transfer_id': 'garbage'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_not_allowed(self):
        url = url_with_transfer_id('ownership-declined')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
