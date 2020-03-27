from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from mock import patch, Mock, call, ANY
from d4s2_api.models import *
from gcb_web_auth.models import DDSEndpoint, DDSUserCredential
from django.contrib.auth.models import User as django_user
from gcb_web_auth.tests_dukeds_auth import ResponseStatusCodeTestCase


class DeliveryIntegrationTestCase(APITestCase, ResponseStatusCodeTestCase):

    def setUp(self):
        """
        Setup two user sender and receiver. Sender has delivery and accepted email templates. Both users
        have DDSUserCredentials setup.
        """
        dds_endpoint = DDSEndpoint.objects.create(
            name='name', agent_key='somekey',
            api_root='https://api.dataservice.duke.edu/api/v1',
            portal_root='https://dataservice.duke.edu',
            openid_provider_id='123',
            openid_provider_service_id='456',
            is_default=True)

        self.sender_username = 'api_user_sender'
        self.sender_email = 'sender@d4s2.com'
        self.sender_dds_id = 'dds_id_sender'
        self.sender_password = 'secret1'
        self.sender_user = django_user.objects.create_user(self.sender_username, password=self.sender_username,
                                                           email=self.sender_email)
        self.sender_email_template_set = EmailTemplateSet.objects.create(name='senderset')
        self.sender_user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.sender_user, email_template_set=self.sender_email_template_set)
        self.delivery_sender_template = EmailTemplate.objects.create(
            template_set=self.sender_email_template_set,
            owner=self.sender_user,
            template_type=EmailTemplateType.objects.get(name='delivery'),
            subject='Sender Delivery Subject',
            body='Sender Delivery Body')
        self.accepted_sender_template = EmailTemplate.objects.create(
            template_set=self.sender_email_template_set,
            owner=self.sender_user,
            template_type=EmailTemplateType.objects.get(name='accepted'),
            subject='Sender Delivery Accepted Subject',
            body='Sender Delivery Accepted Body')
        self.accepted_sender_template = EmailTemplate.objects.create(
            template_set=self.sender_email_template_set,
            owner=self.sender_user,
            template_type=EmailTemplateType.objects.get(name='accepted_recipient'),
            subject='Sender Delivery Accepted To Recipient Subject',
            body='Sender Delivery Accepted To Recipient Body')
        self.declined_sender_template = EmailTemplate.objects.create(
            template_set=self.sender_email_template_set,
            owner=self.sender_user,
            template_type=EmailTemplateType.objects.get(name='declined'),
            subject='Sender Delivery Declined',
            body='Sender Delivery Declined Body')

        DDSUserCredential.objects.create(endpoint=dds_endpoint, user=self.sender_user, token='123', dds_id='456')

        self.recipient_username = 'api_user_recipient'
        self.recipient_email = 'recipient@d4s2.com'
        self.recipient_dds_id = 'dds_id_recipient'
        self.recipient_password = 'secret2'
        self.recipient_user = django_user.objects.create_user(self.recipient_username, password=self.recipient_password,
                                                              email=self.recipient_email)
        DDSUserCredential.objects.create(endpoint=dds_endpoint, user=self.recipient_user, token='789', dds_id='999')

        self.reply_to_email = 'replyto@d4s2.com'
        self.cc_email = 'cc@d4s2.com'

    def login_as_sender(self):
        self.client.force_login(self.sender_user)

    def login_as_recipient(self):
        self.client.force_login(self.recipient_user)

    def dds_user_fetch_one(self, ddsutil, user_id):
        if user_id == self.sender_dds_id:
            return Mock(full_name='Sender', email=self.sender_user.email)
        if user_id == self.recipient_dds_id:
            return Mock(full_name='Recipient', email=self.recipient_user.email)
        raise ValueError("Invalid user id:" + user_id)

    @patch('d4s2_api_v1.api.DDSUtil', autospec=True)
    @patch('switchboard.dds_util.DDSUser', autospec=True)
    @patch('switchboard.dds_util.DDSProjectTransfer', autospec=True)
    @patch('switchboard.dds_util.RemoteStore', autospec=True)
    @patch('d4s2_api.utils.Message', autospec=True)
    def test_accepted_delivery_uses_senders_email_template_set(self, mock_message, mock_remote_store,
                                                               mock_project_transfer, mock_dds_user, mock_dds_util):
        mock_dds_util.return_value.create_project_transfer.return_value = {'id': 'transfer_1'}
        mock_dds_user.fetch_one = self.dds_user_fetch_one
        mock_remote_store.return_value.data_service = Mock()
        mock_message.return_value = Mock(email_text='')
        mock_project_transfer.fetch_one.return_value.project_dict = {'name': 'MouseRNA'}

        self.login_as_sender()

        # sender creates a delivery
        url = reverse('ddsdelivery-list')
        data = {
            'project_id': 'project-1',
            'from_user_id': self.sender_dds_id,
            'to_user_id': self.recipient_dds_id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NEW)

        # sender sends the delivery
        url = reverse('ddsdelivery-send', args=(dds_delivery.pk,))
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NOTIFIED)

        # we should have sent one email from the sender to the recipient with sender delivery content
        self.assertEqual(mock_message.mock_calls, [
            call(self.sender_email, self.recipient_email, 'Sender Delivery Subject', 'Sender Delivery Body', ANY, None),
            call().send(),
        ])
        mock_message.reset_mock()

        self.client.logout()
        self.login_as_recipient()

        # Recipient processes the delivery and accepts ownership
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': 'transfer_1'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.ACCEPTED)

        # Recipient has no email templates
        self.assertEqual(UserEmailTemplateSet.objects.filter(user=self.recipient_user).count(), 0)

        # we should have sent one email from the recipient to the sender with senders accepted content
        self.assertEqual(mock_message.mock_calls, [
            call(self.recipient_email, self.sender_email, 'Sender Delivery Accepted Subject',
                 'Sender Delivery Accepted Body', ANY, None),
            call(self.sender_email, self.recipient_email, 'Sender Delivery Accepted To Recipient Subject',
                 'Sender Delivery Accepted To Recipient Body', ANY, None),
            call().send(),
            call().send()
        ])

    @patch('d4s2_api_v1.api.DDSUtil', autospec=True)
    @patch('switchboard.dds_util.DDSUser', autospec=True)
    @patch('switchboard.dds_util.DDSProjectTransfer', autospec=True)
    @patch('switchboard.dds_util.RemoteStore', autospec=True)
    @patch('d4s2_api.utils.Message', autospec=True)
    def test_declined_delivery_uses_senders_email_template_set(self, mock_message, mock_remote_store,
                                                               mock_project_transfer, mock_dds_user, mock_dds_util):
        mock_dds_util.return_value.create_project_transfer.return_value = {'id': 'transfer_1'}
        mock_dds_user.fetch_one = self.dds_user_fetch_one
        mock_message.return_value = Mock(email_text='')
        mock_remote_store.return_value.data_service = Mock()

        self.login_as_sender()

        # sender creates a delivery
        url = reverse('ddsdelivery-list')
        data = {
            'project_id': 'project-1',
            'from_user_id': self.sender_dds_id,
            'to_user_id': self.recipient_dds_id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NEW)

        # sender sends the delivery
        url = reverse('ddsdelivery-send', args=(dds_delivery.pk,))
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NOTIFIED)

        # we should have sent one email from the sender to the recipient with sender delivery content
        self.assertEqual(mock_message.mock_calls, [
            call(self.sender_email, self.recipient_email, 'Sender Delivery Subject', 'Sender Delivery Body', ANY, None),
            call().send()
        ])
        mock_message.reset_mock()

        self.client.logout()
        self.login_as_recipient()

        # Recipient declines the delivery/ownership
        url = reverse('ownership-decline')
        response = self.client.post(url, {'transfer_id': 'transfer_1', 'decline_reason': 'Wrong person'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.DECLINED)

        # Recipient has no email templates
        self.assertEqual(UserEmailTemplateSet.objects.filter(user=self.recipient_user).count(), 0)

        # we should have sent one email from the recipient to the sender with recipient declined content
        self.assertEqual(mock_message.mock_calls, [
            call(self.recipient_email, self.sender_email, 'Sender Delivery Declined',
                 'Sender Delivery Declined Body', ANY, None),
            call().send(),
        ])

    @patch('d4s2_api_v1.api.DDSUtil', autospec=True)
    @patch('switchboard.dds_util.DDSUser', autospec=True)
    @patch('switchboard.dds_util.DDSProjectTransfer', autospec=True)
    @patch('switchboard.dds_util.RemoteStore', autospec=True)
    @patch('d4s2_api.utils.Message', autospec=True)
    def test_delivery_uses_template_reply_to(self, mock_message, mock_remote_store,
                                                               mock_project_transfer, mock_dds_user, mock_dds_util):
        self.sender_email_template_set.reply_address = self.reply_to_email
        self.sender_email_template_set.save()

        mock_dds_util.return_value.create_project_transfer.return_value = {'id': 'transfer_1'}
        mock_dds_user.fetch_one = self.dds_user_fetch_one
        mock_remote_store.return_value.data_service = Mock()
        mock_message.return_value = Mock(email_text='')

        self.login_as_sender()

        # sender creates a delivery
        url = reverse('ddsdelivery-list')
        data = {
            'project_id': 'project-1',
            'from_user_id': self.sender_dds_id,
            'to_user_id': self.recipient_dds_id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NEW)

        # sender sends the delivery
        url = reverse('ddsdelivery-send', args=(dds_delivery.pk,))
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NOTIFIED)

        # we should have sent one email from the sender to the recipient with sender delivery content
        self.assertEqual(mock_message.mock_calls, [
            call(self.reply_to_email, self.recipient_email, 'Sender Delivery Subject', 'Sender Delivery Body', ANY, None),
            call().send(),
        ])
        mock_message.reset_mock()
        self.client.logout()

    @patch('d4s2_api_v1.api.DDSUtil', autospec=True)
    @patch('switchboard.dds_util.DDSUser', autospec=True)
    @patch('switchboard.dds_util.DDSProjectTransfer', autospec=True)
    @patch('switchboard.dds_util.RemoteStore', autospec=True)
    @patch('d4s2_api.utils.Message', autospec=True)
    def test_delivery_and_acceptance_use_template_cc(self, mock_message, mock_remote_store,
                                             mock_project_transfer, mock_dds_user, mock_dds_util):
        self.sender_email_template_set.cc_address = self.cc_email
        self.sender_email_template_set.save()

        mock_dds_util.return_value.create_project_transfer.return_value = {'id': 'transfer_1'}
        mock_dds_user.fetch_one = self.dds_user_fetch_one
        mock_remote_store.return_value.data_service = Mock()
        mock_message.return_value = Mock(email_text='')
        mock_project_transfer.fetch_one.return_value.project_dict = {'name': 'MouseRNA'}

        self.login_as_sender()

        # sender creates a delivery
        url = reverse('ddsdelivery-list')
        data = {
            'project_id': 'project-1',
            'from_user_id': self.sender_dds_id,
            'to_user_id': self.recipient_dds_id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NEW)

        # sender sends the delivery
        url = reverse('ddsdelivery-send', args=(dds_delivery.pk,))
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.NOTIFIED)

        # we should have sent one email from the sender to the recipient with sender delivery content
        self.assertEqual(mock_message.mock_calls, [
            call(self.sender_email, self.recipient_email, 'Sender Delivery Subject', 'Sender Delivery Body', ANY, self.cc_email),
            call().send(),
        ])
        mock_message.reset_mock()

        self.client.logout()
        self.login_as_recipient()

        # Recipient processes the delivery and accepts ownership
        url = reverse('ownership-process')
        response = self.client.post(url, {'transfer_id': 'transfer_1'})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.state, State.ACCEPTED)
        self.assertEqual(dds_delivery.project_name, 'MouseRNA')

        # Recipient has no email templates
        self.assertEqual(UserEmailTemplateSet.objects.filter(user=self.recipient_user).count(), 0)

        # we should have sent one email from the recipient to the sender with senders accepted content
        self.assertEqual(mock_message.mock_calls, [
            call(self.recipient_email, self.sender_email, 'Sender Delivery Accepted Subject',
                 'Sender Delivery Accepted Body', ANY, self.cc_email),
            call(self.sender_email, self.recipient_email, 'Sender Delivery Accepted To Recipient Subject',
                 'Sender Delivery Accepted To Recipient Body', ANY, self.cc_email),
            call().send(),
            call().send()
        ])
