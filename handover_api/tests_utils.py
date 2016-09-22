from mock import patch, Mock, MagicMock
from django.test import TestCase
from handover_api.utils import perform_handover, HandoverMessage
from handover_api.models import Handover, DukeDSProject, DukeDSUser
from django.contrib.auth.models import User, Group

class UtilsTestCaseHandover(TestCase):

    def setUp(self):
        # Email templates are tied to groups and users
        group = Group.objects.create(name='test_group')
        user = User.objects.create(username='test_user')
        group.user_set.add(user)
        from_user = DukeDSUser.objects.create(dds_id='abc123', user=user)
        to_user = DukeDSUser.objects.create(dds_id='def456')
        project = DukeDSProject.objects.create(project_id='ghi789')
        self.h = Handover.objects.create(from_user=from_user, to_user=to_user, project=project)

    @patch('handover_api.utils.DDSUtil')
    def test_perform_handover(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        h = self.h
        perform_handover(h)
        MockDDSUtil.assert_any_call(h.from_user.dds_id)
        mock_ddsutil.add_user.assert_called_with(h.to_user.dds_id, h.project.project_id, 'project_admin')

    @patch('handover_api.utils.HandoverDetails')
    def test_email_templating(self, MockHandoverDetails):
        mock_details = MockHandoverDetails()
        mock_details.get_from_user = Mock(return_value=MagicMock(full_name='From User',email='from@host.com'))
        mock_details.get_to_user = Mock(return_value=MagicMock(full_name='To User', email='to@host.com'))
        project_mock = Mock(spec='name')
        project_mock.name = 'Project 123' # Can't make a MagicMock with a name keyword
        mock_details.get_project = Mock(return_value=project_mock)
        templates = ('{{ project_name }}','Hi, {{ recipient_name }}. data at {{ url }}')
        mock_details.get_email_template_text = Mock(return_value=templates)
        message = HandoverMessage(self.h, 'http://localhost/accept')
        self.assertEqual(mock_details.get_project.call_count, 1)
        self.assertEqual(mock_details.get_from_user.call_count, 1)
        self.assertEqual(mock_details.get_to_user.call_count, 1)
        self.assertIn('Subject: Project 123', message.email_text)
        self.assertIn('Hi, To User. data at http://localhost/accept', message.email_text)

