from mock import patch, Mock
from django.test import TestCase
from d4s2_api.utils import perform_delivery, DeliveryMessage
from d4s2_api.models import Delivery, DukeDSProject, DukeDSUser
from ownership.test_views import setup_mock_delivery_details
from django.contrib.auth.models import User, Group


class UtilsTestCaseDelivery(TestCase):

    def setUp(self):
        # Email templates are tied to groups and users
        group = Group.objects.create(name='test_group')
        self.user = User.objects.create(username='test_user')
        group.user_set.add(self.user)
        from_user = DukeDSUser.objects.create(dds_id='abc123', user=self.user)
        to_user = DukeDSUser.objects.create(dds_id='def456')
        project = DukeDSProject.objects.create(project_id='ghi789')
        self.h = Delivery.objects.create(from_user=from_user, to_user=to_user, project=project)

    @patch('d4s2_api.utils.DDSUtil')
    def test_perform_delivery(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        h = self.h
        perform_delivery(h, self.user)
        MockDDSUtil.assert_any_call(h.from_user.dds_id)
        mock_ddsutil.add_user.assert_called_with(h.to_user.dds_id, h.project.project_id, 'project_admin')

    @patch('d4s2_api.utils.DeliveryDetails')
    def test_email_templating(self, MockDeliveryDetails):
        setup_mock_delivery_details(MockDeliveryDetails)
        mock_details = MockDeliveryDetails()
        message = DeliveryMessage(self.h, 'http://localhost/accept')
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertIn('Subject Template project', message.email_text)
        self.assertIn('Body Template bob', message.email_text)
