from django.test import TestCase
from d4s2_api.models import DukeDSUser, DukeDSProject
from mock import patch, Mock, MagicMock
from switchboard.dds_util import DDSUtil, ModelPopulator, DeliveryDetails, get_local_dds_token, get_dds_token_from_oauth, NoTokenException
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from d4s2_api.models import User
from d4s2_auth.tests_oauth_utils import make_oauth_service
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


class DDSUtilAuthTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'
        self.token = DukeDSAPIToken.objects.create(user=self.user, key='some-token')
        self.oauth_service = OAuthService.objects.create(name="Test Service")

    @patch('switchboard.dds_util.check_jwt_token')
    def test_reads_local_token(self, mock_check_jwt_token):
        mock_check_jwt_token.return_value = True
        local_token = get_local_dds_token(self.user)
        self.assertEqual(local_token.key, 'some-token', 'Should return token when check passes')

    @patch('switchboard.dds_util.check_jwt_token')
    def test_no_local_token_when_check_fails(self, mock_check_jwt_token):
        mock_check_jwt_token.return_value = False
        local_token = get_local_dds_token(self.user)
        self.assertIsNone(local_token, 'Should return none when check fails')

    @patch('switchboard.dds_util.requests')
    def test_gets_dds_token_from_oauth(self, mock_requests):
        mocked_dds_token = {'api_token': 'abc1234'}
        mock_response = Mock(raise_for_status=Mock(), json=Mock(return_value=mocked_dds_token))
        mock_requests.get = Mock(return_value=mock_response)
        oauth_token = OAuthToken.objects.create(user=self.user,
                                                service=self.oauth_service,
                                                token_json='{"access_token":"g2jo83lmvasijgq"}')
        exchanged = get_dds_token_from_oauth(oauth_token)
        # Should parse the JSON of the oauth_token and send the value of access_token to the DDS API
        sent_get_params = mock_requests.get.call_args[1].get('params')
        self.assertEqual(sent_get_params['access_token'], 'g2jo83lmvasijgq')
        self.assertTrue(mock_requests.get.called)
        self.assertTrue(mock_response.raise_for_status.called)
        self.assertEqual(exchanged, mocked_dds_token)

    @patch('switchboard.dds_util.requests')
    def test_handles_dds_token_from_oauth_failure(self, mock_requests):
        mock_requests.HTTPError = Exception
        mocked_dds_token = {'api_token': 'abc1234'}
        raise_for_status = Mock()
        raise_for_status.side_effect = mock_requests.HTTPError()
        mock_response = Mock(raise_for_status=raise_for_status)
        mock_requests.get = Mock(return_value=mock_response)
        oauth_token = OAuthToken.objects.create(user=self.user,
                                                service=self.oauth_service,
                                                token_json='{"access_token":"g2jo83lmvasijgq"}')
        with self.assertRaises(NoTokenException):
            get_dds_token_from_oauth(oauth_token)

class MockDetails(object):
    full_name='Test User'
    email='test@example.com'
    project_name='My Project'

def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = Mock()
    mock_ddsutil.return_value.get_remote_user = Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser(MockDetails.full_name, MockDetails.email)
    mock_ddsutil.return_value.get_remote_project.return_value = MockDDSProject(MockDetails.project_name)


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
