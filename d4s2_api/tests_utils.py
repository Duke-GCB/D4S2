from mock import patch, Mock
from django.test import TestCase
from d4s2_api.utils import accept_delivery, decline_delivery, ShareMessage, DeliveryMessage, ProcessedMessage
from d4s2_api.models import Delivery, Share, DukeDSProject, DukeDSUser
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
        project = DukeDSProject.objects.create(project_id='ghi789')
        self.delivery = Delivery.objects.create(from_user=from_user, to_user=to_user, project=project)
        self.share = Share.objects.create(from_user=from_user, to_user=to_user, project=project)

    @patch('d4s2_api.utils.DDSUtil')
    def test_accept_delivery(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.accept_project_transfer = Mock()
        delivery = self.delivery
        accept_delivery(delivery, self.user)
        MockDDSUtil.assert_any_call(self.user)
        mock_ddsutil.accept_project_transfer.assert_called_with(delivery.transfer_id)

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
        message = DeliveryMessage(self.delivery, 'http://localhost/accept')
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
        message = ShareMessage(self.share)
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
        message = ProcessedMessage(self.delivery, process_type, reason)
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertEqual(mock_details.get_user_message.call_count, 1)
        self.assertEqual(mock_details.get_action_template_text.call_count, 1)
        self.assertTrue(mock_details.get_action_template_text.called_with('process_type'))
        self.assertIn('Action Subject Template project', message.email_text)
        self.assertIn('Action Body Template bob', message.email_text)
        self.assertIn('Action User Message msg', message.email_text)

