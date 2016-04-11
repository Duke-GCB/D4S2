from mock import patch, Mock
from django.test import TestCase
from handover_api.utils import perform_handover, get_accept_url
from handover_api.models import Handover

class UtilsTestCaseHandover(TestCase):
    def setUp(self):
        self.h = Handover.objects.create(from_user_id='abc123', to_user_id='def456', project_id='ghi789')

    @patch('handover_api.utils.DDSUtil')
    def test_perform_handover(self, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.add_user = Mock()
        mock_ddsutil.remove_user = Mock()
        h = self.h
        perform_handover(h)
        MockDDSUtil.assert_any_call(h.from_user_id)
        mock_ddsutil.add_user.assert_called_with(h.to_user_id, h.project_id, 'project_admin')
        MockDDSUtil.assert_any_call(h.to_user_id)
        mock_ddsutil.remove_user.assert_called_with(h.from_user_id, h.project_id)

    def test_get_accept_url(self):
        url = get_accept_url(self.h, "http://localhost")
        self.assertIn(str(self.h.token), url)


