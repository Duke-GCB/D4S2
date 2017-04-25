from django.test import TestCase
from d4s2_api.models import DukeDSUser, DukeDSProject
from mock import patch, Mock, MagicMock
from switchboard.dds_util import DDSUtil, ModelPopulator, DeliveryDetails
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from d4s2_api.models import User
from d4s2_auth.oauth_utils import get_local_dds_token, get_dds_token_from_oauth, NoTokenException
from d4s2_auth.models import OAuthService, DukeDSAPIToken, OAuthToken


class DDSUtilTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'

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
        # DukeDSUser.objects.create(dds_id=self.user_id)
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
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
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user)
            self.assertEqual(ddsutil.get_remote_project(project_id).name, project_name)
            self.assertTrue(instance.fetch_remote_project_by_id.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testAddUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        DukeDSUser.objects.create(dds_id=self.user_id)
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user)
            ddsutil.add_user('userid','projectid','auth_role')
            self.assertTrue(instance.set_user_project_permission.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testRemoveUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        DukeDSUser.objects.create(dds_id=self.user_id)
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user)
            ddsutil.remove_user('userid','projectid')
            self.assertTrue(instance.revoke_user_project_permission.called)

    def testFailsWithoutUser(self):
        with self.settings(DDSCLIENT_PROPERTIES={}):
            self.assertEqual(len(DukeDSUser.objects.all()), 0)
            with self.assertRaises(ValueError):
                ddsutil = DDSUtil('')
                ddsutil.remote_store

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProjectTransfer(self, mockRemoteStore):
        transfer_id = 'abvcca-123'
        mock_project_transfer = {'id': transfer_id, 'status': 'accepted'}
        get_project_transfer = MagicMock(return_value=MagicMock(json=MagicMock(return_value=mock_project_transfer)))
        mockRemoteStore.return_value = MagicMock(data_service=MagicMock(get_project_transfer=get_project_transfer))
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user)
            project_transfer = ddsutil.get_project_transfer(transfer_id)
            self.assertTrue(get_project_transfer.called_with(transfer_id))
            self.assertEqual(project_transfer.get('status'), 'accepted')


class MockDetails(object):
    full_name='Test User'
    email='test@example.com'
    project_name='My Project'

def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser(MockDetails.full_name, MockDetails.email)
    mock_ddsutil.return_value.get_remote_project.return_value = MockDDSProject(MockDetails.project_name)
    mock_ddsutil.return_value.get_project_transfer.return_value = {'id': 'transfer-abc', 'status': 'rejected', 'status_comment': 'Bad Data'}


# Test model populator
class TestModelPopulator(TestCase):
    @patch('switchboard.dds_util.DDSUtil')
    def test_populate_user(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        u = DukeDSUser.objects.create(dds_id='abcd-1234')
        self.assertFalse(u.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_user(u)
        self.assertTrue(u.populated())
        self.assertTrue(dds_util.get_remote_user.called)
        self.assertTrue(dds_util.get_remote_user.called_with('abcd-1234'))
        self.assertEqual(u.full_name, MockDetails.full_name)
        self.assertEqual(u.email, MockDetails.email)

    @patch('switchboard.dds_util.DDSUtil')
    def test_skips_populated_user(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        u = DukeDSUser.objects.create(dds_id='abcd-1234', full_name='Test User', email='test@example.com')
        self.assertTrue(u.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_user(u)
        self.assertTrue(u.populated())
        self.assertFalse(dds_util.get_remote_user.called)


    @patch('switchboard.dds_util.DDSUtil')
    def test_populate_project(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        p = DukeDSProject.objects.create(project_id='1234-defg')
        self.assertFalse(p.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_project(p)
        self.assertTrue(p.populated())
        self.assertTrue(dds_util.get_remote_project.called)
        self.assertTrue(dds_util.get_remote_project.called_with('1234-defg'))
        self.assertEqual(p.name, MockDetails.project_name)

    @patch('switchboard.dds_util.DDSUtil')
    def test_skips_populated_project(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        p = DukeDSProject.objects.create(project_id='1234-defg', name='My project')
        self.assertTrue(p.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_project(p)
        self.assertTrue(p.populated())
        self.assertFalse(dds_util.get_remote_project.called)

    @patch('switchboard.dds_util.DDSUtil')
    def test_update_delivery(self, mock_dds_util):
        mock_delivery = Mock()
        mock_delivery.return_value.update_state_from_project_transfer = Mock()
        mock_delivery.return_value.transfer_id = 'transfer_id'
        delivery = mock_delivery()
        setup_mock_ddsutil(mock_dds_util)
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.update_delivery(delivery)
        self.assertTrue(dds_util.get_project_transfer.called_with('transfer_id'))
        self.assertTrue(delivery.update_state_from_project_transfer.called)


class TestDeliveryDetails(TestCase):

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_share_template(self, MockEmailTemplate):
        MockEmailTemplate.for_share = Mock(return_value=MagicMock(subject='share subject', body='share body'))
        delivery = Mock()
        details = DeliveryDetails(delivery)
        subject, body = details.get_share_template_text()
        self.assertTrue(MockEmailTemplate.for_share.called_with(delivery))
        self.assertEqual(subject, 'share subject')
        self.assertEqual(body, 'share body')

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_action_template(self, MockEmailTemplate):
        MockEmailTemplate.for_operation = Mock(return_value=MagicMock(subject='action subject', body='action body'))
        delivery = Mock()
        details = DeliveryDetails(delivery)
        subject, body = details.get_action_template_text('accepted')
        self.assertEqual(subject, 'action subject')
        self.assertEqual(body, 'action body')
        self.assertTrue(MockEmailTemplate.for_operation.called_with(delivery, 'accepted'))
