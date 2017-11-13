from mock import patch, Mock, call
from django.test import TestCase
from d4s2_api.utils import decline_delivery, ShareMessage, DeliveryMessage, ProcessedMessage, \
    MessageDirection, DeliveryUtil
from d4s2_api.models import Delivery, Share, DukeDSProject, DukeDSUser, State
from ownership.test_views import setup_mock_delivery_details
from django.contrib.auth.models import User, Group


class UtilsTestCase(TestCase):

    def setUp(self):
        # Email templates are tied to groups and users
        group = Group.objects.create(name='test_group')
        self.user = User.objects.create(username='test_user')
        group.user_set.add(self.user)
        from_user = DukeDSUser.objects.create(dds_id='abc123', user=self.user)
        to_user = DukeDSUser.objects.create(dds_id='def456')
        share_user1 = DukeDSUser.objects.create(dds_id='jkl888')
        share_user2 = DukeDSUser.objects.create(dds_id='mno999')
        project = DukeDSProject.objects.create(project_id='ghi789')
        self.delivery = Delivery.objects.create(from_user=from_user, to_user=to_user, project=project)
        self.delivery.share_to_users = [share_user1, share_user2 ]
        self.delivery.save()
        self.share = Share.objects.create(from_user=from_user, to_user=to_user, project=project)

    @patch('d4s2_api.utils.DDSUtil')
    def test_decline_delivery(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.decline_project_transfer = Mock()
        delivery = self.delivery
        decline_delivery(delivery, self.user, 'reason')
        MockDDSUtil.assert_any_call(self.user)
        mock_ddsutil.decline_project_transfer.assert_called_with(delivery.transfer_id, 'reason')

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_delivery_message(self, MockDeliveryDetails):
        mock_details = setup_mock_delivery_details(MockDeliveryDetails)
        message = DeliveryMessage(self.delivery, self.user, 'http://localhost/accept')
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertEqual(mock_details.get_user_message.call_count, 1)
        self.assertEqual(mock_details.get_action_template_text.call_count, 1)
        self.assertTrue(mock_details.get_action_template_text.called_with('delivery'))
        self.assertIn('Action Subject Template project', message.email_text)
        self.assertIn('Action Body Template bob', message.email_text)
        self.assertIn('Action User Message msg', message.email_text)

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_share_message(self, MockDeliveryDetails):
        mock_details = setup_mock_delivery_details(MockDeliveryDetails)
        message = ShareMessage(self.share, self.user)
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertEqual(mock_details.get_user_message.call_count, 1)
        self.assertEqual(mock_details.get_share_template_text.call_count, 1)
        self.assertIn('Share Subject Template project', message.email_text)
        self.assertIn('Share Body Template bob', message.email_text)
        self.assertIn('Share User Message msg', message.email_text)

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_processed_message(self, MockDeliveryDetails):
        mock_details = setup_mock_delivery_details(MockDeliveryDetails)
        process_type = 'decline'
        reason = 'sample reason'
        message = ProcessedMessage(self.delivery, self.user, process_type, reason)
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertEqual(mock_details.get_user_message.call_count, 1)
        self.assertEqual(mock_details.get_action_template_text.call_count, 1)
        self.assertTrue(mock_details.get_action_template_text.called_with('process_type'))
        self.assertIn('Action Subject Template project', message.email_text)
        self.assertIn('Action Body Template bob', message.email_text)
        self.assertIn('Action User Message msg', message.email_text)

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_message_direction_share(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        message = ShareMessage(self.share, self.user)
        self.assertEqual(message.email_receipients, ['bob@joe.com'], 'Share message should go to delivery recipient')
        self.assertEqual(message.email_from, 'joe@joe.com', 'Share message should be from delivery sender')

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_message_direction_delivery(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        message = DeliveryMessage(self.share, self.user, 'http://localhost/accept')
        self.assertEqual(message.email_receipients, ['bob@joe.com'], 'Delivery message go to delivery recipient')
        self.assertEqual(message.email_from, 'joe@joe.com', 'Delivery message should be from delivery sender')

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_message_direction_processed(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        process_type = 'decline'
        reason = 'sample reason'
        message = ProcessedMessage(self.delivery, self.user, process_type, reason)
        self.assertEqual(message.email_receipients, ['joe@joe.com'], 'Processed message should go to delivery sender')
        self.assertEqual(message.email_from, 'bob@joe.com', 'Processed message should be from delivery recipient')


class MessageDirectionTestCase(TestCase):

    def setUp(self):
        self.sender_email = 'sender@email.com'
        self.receiver_email = 'receiver@email.com'
        self.sender = Mock(email=self.sender_email)
        self.receiver = Mock(email=self.receiver_email)

    def test_default_order(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender, self.receiver)
        self.assertEqual(ordered_addresses, (self.sender_email, self.receiver_email))

    def test_orders_forward(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender, self.receiver, MessageDirection.ToRecipient)
        self.assertEqual(ordered_addresses, (self.sender_email, self.receiver_email))

    def test_orders_reverse(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender, self.receiver, MessageDirection.ToSender)
        self.assertEqual(ordered_addresses, (self.receiver_email, self.sender_email))


class DeliveryUtilTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_user')
        from_user = DukeDSUser.objects.create(dds_id='abc123', user=self.user)
        to_user = DukeDSUser.objects.create(dds_id='def456')
        self.share_user1 = DukeDSUser.objects.create(dds_id='jkl888')
        self.share_user2 = DukeDSUser.objects.create(dds_id='mno999')
        self.project = DukeDSProject.objects.create(project_id='ghi789')
        self.delivery = Delivery.objects.create(from_user=from_user, to_user=to_user, project=self.project)
        self.delivery.share_to_users = [self.share_user1, self.share_user2 ]
        self.delivery.save()

    @patch('d4s2_api.utils.DDSUtil')
    def test_accept_project_transfer(self, mock_ddsutil):
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.accept_project_transfer()
        mock_ddsutil.return_value.accept_project_transfer.assert_called_with(self.delivery.transfer_id)

    @patch('d4s2_api.utils.DDSUtil')
    @patch('d4s2_api.utils.DeliveryDetails')
    def test_share_with_additional_users(self, mock_delivery_details, mock_ddsutil):
        mock_delivery_details.return_value.get_share_template_text.return_value = 'subject', 'template body'
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.share_with_additional_users()

        # each additional user should have permissions given
        mock_ddsutil.return_value.share_project_with_user.assert_has_calls([
            call('ghi789', 'jkl888', 'file_downloader'),
            call('ghi789', 'mno999', 'file_downloader'),
        ])

        # each additional user should have an email sent (share record)
        share1 = Share.objects.get(to_user=self.share_user1)
        self.assertEqual(self.project, share1.project)
        self.assertEqual(self.delivery.to_user, share1.from_user)
        self.assertEqual(State.NOTIFIED, share1.state)
        share2 = Share.objects.get(to_user=self.share_user2)
        self.assertEqual(self.project, share2.project)
        self.assertEqual(self.delivery.to_user, share2.from_user)
        self.assertEqual(State.NOTIFIED, share2.state)
