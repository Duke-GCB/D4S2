from mock import patch, Mock
from django.test import TestCase
from handover_api.utils import perform_handover
from handover_api.models import Handover, DukeDSProject, DukeDSUser

class UtilsTestCaseHandover(TestCase):
    def setUp(self):
        from_user = DukeDSUser.objects.create(dds_id='abc123')
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
