from django.test import TestCase
from d4s2_api.models import DukeDSUser
from mock import patch, Mock, MagicMock
from switchboard.dds_util import DDSUtil, DeliveryDetails
from d4s2_api.models import User
from gcb_web_auth.models import DukeDSSettings


class DDSUtilTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'
        DukeDSSettings.objects.create(url='', portal_root='', openid_provider_id='')

        patcher = patch('switchboard.dds_util.get_dds_token')
        mock_get_dds_token = patcher.start()
        mock_get_dds_token.return_value = MagicMock(key='sometoken')
        self.addCleanup(patcher.stop)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetEmail(self, mockRemoteStore):
        email = 'example@domain.com'
        # Mock a remote user object, and bind it to fetch_user
        remote_user = Mock()
        remote_user.email = email
        instance = mockRemoteStore.return_value
        instance.fetch_user.return_value = remote_user
        ddsutil = DDSUtil(self.user)
        self.assertEqual(email, ddsutil.get_remote_user(self.user_id).email)
        self.assertTrue(instance.fetch_user.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProject(self, mockRemoteStore):
        project_id = '8677-11231-44414-4442'
        project_name = 'Project ABC'
        remote_project = Mock()
        remote_project.name = project_name
        instance = mockRemoteStore.return_value
        instance.fetch_remote_project_by_id.return_value = remote_project
        DukeDSUser.objects.create(dds_id=self.user_id)
        ddsutil = DDSUtil(self.user)
        self.assertEqual(ddsutil.get_remote_project(project_id).name, project_name)
        self.assertTrue(instance.fetch_remote_project_by_id.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testAddUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        DukeDSUser.objects.create(dds_id=self.user_id)
        ddsutil = DDSUtil(self.user)
        ddsutil.add_user('userid','projectid','auth_role')
        self.assertTrue(instance.set_user_project_permission.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testRemoveUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        DukeDSUser.objects.create(dds_id=self.user_id)
        ddsutil = DDSUtil(self.user)
        ddsutil.remove_user('userid','projectid')
        self.assertTrue(instance.revoke_user_project_permission.called)

    def testFailsWithoutUser(self):
        self.assertEqual(len(DukeDSUser.objects.all()), 0)
        with self.assertRaises(ValueError):
            ddsutil = DDSUtil('')
            ddsutil.remote_store

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProjectTransfer(self, mockRemoteStore):
        mock_requests_response = MagicMock()
        transfer_id = 'abvcca-123'
        get_project_transfer = mockRemoteStore.return_value.data_service.get_project_transfer
        get_project_transfer.return_value = mock_requests_response
        ddsutil = DDSUtil(self.user)
        project_transfer_response = ddsutil.get_project_transfer(transfer_id)
        self.assertTrue(get_project_transfer.called_with(transfer_id))
        self.assertEqual(project_transfer_response, mock_requests_response)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProjectTransfers(self, mockRemoteStore):
        mock_requests_response = MagicMock()
        mock_data_service = mockRemoteStore.return_value.data_service
        mock_data_service.get_all_project_transfers.return_value = mock_requests_response
        ddsutil = DDSUtil(self.user)
        project_transfers_response = ddsutil.get_project_transfers()
        self.assertTrue(mock_data_service.get_all_project_transfers.called)
        self.assertEqual(project_transfers_response, mock_requests_response)


class TestDeliveryDetails(TestCase):

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_share_template(self, MockEmailTemplate):
        MockEmailTemplate.for_share = Mock(return_value=MagicMock(subject='share subject', body='share body'))
        delivery = Mock()
        user = Mock()
        details = DeliveryDetails(delivery, user)
        subject, body = details.get_share_template_text()
        self.assertTrue(MockEmailTemplate.for_share.called_with(delivery))
        self.assertEqual(subject, 'share subject')
        self.assertEqual(body, 'share body')

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_action_template(self, MockEmailTemplate):
        MockEmailTemplate.for_operation = Mock(return_value=MagicMock(subject='action subject', body='action body'))
        delivery = Mock()
        user = Mock()
        details = DeliveryDetails(delivery, user)
        subject, body = details.get_action_template_text('accepted')
        self.assertEqual(subject, 'action subject')
        self.assertEqual(body, 'action body')
        self.assertTrue(MockEmailTemplate.for_operation.called_with(delivery, 'accepted'))
