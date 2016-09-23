from django.test import TestCase
from d4s2_api.models import DukeDSUser, DukeDSProject
from django.core.exceptions import ObjectDoesNotExist
import mock
from switchboard.dds_util import DDSUtil, ModelPopulator, DeliveryDetails
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser


class DDSUtilTestCase(TestCase):
    def setUp(self):
        self.user_id = 'abcd-1234-efgh-8876'

    @mock.patch('switchboard.dds_util.RemoteStore')
    def testGetEmail(self, mockRemoteStore):
        email = 'example@domain.com'
        # Mock a remote user object, and bind it to fetch_user
        remote_user = mock.Mock()
        remote_user.email = email
        instance = mockRemoteStore.return_value
        instance.fetch_user.return_value = remote_user
        DukeDSUser.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user_id)
            self.assertEqual(email, ddsutil.get_remote_user(self.user_id).email)
            self.assertTrue(instance.fetch_user.called)

    @mock.patch('switchboard.dds_util.RemoteStore')
    def testGetProject(self, mockRemoteStore):
        project_id = '8677-11231-44414-4442'
        project_name = 'Project ABC'
        remote_project = mock.Mock()
        remote_project.name = project_name
        instance = mockRemoteStore.return_value
        instance.fetch_remote_project_by_id.return_value = remote_project
        DukeDSUser.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user_id)
            self.assertEqual(ddsutil.get_remote_project(project_id).name, project_name)
            self.assertTrue(instance.fetch_remote_project_by_id.called)

    @mock.patch('switchboard.dds_util.RemoteStore')
    def testAddUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = mock.Mock()
        DukeDSUser.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user_id)
            ddsutil.add_user('userid','projectid','auth_role')
            self.assertTrue(instance.set_user_project_permission.called)

    @mock.patch('switchboard.dds_util.RemoteStore')
    def testRemoveUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = mock.Mock()
        DukeDSUser.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user_id)
            ddsutil.remove_user('userid','projectid')
            self.assertTrue(instance.revoke_user_project_permission.called)

    def testFailsWithoutAPIKeyUser(self):
        with self.settings(DDSCLIENT_PROPERTIES={}):
            self.assertEqual(len(DukeDSUser.objects.all()), 0)
            with self.assertRaises(ObjectDoesNotExist):
                ddsutil = DDSUtil('abcd-efgh-1234-5678')
                ddsutil.remote_store

class MockDetails(object):
    full_name='Test User'
    email='test@example.com'
    project_name='My Project'

def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = mock.Mock()
    mock_ddsutil.return_value.get_remote_user = mock.Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser(MockDetails.full_name, MockDetails.email)
    mock_ddsutil.return_value.get_remote_project.return_value = MockDDSProject(MockDetails.project_name)


# Test model populator
class TestModelPopulator(TestCase):
    @mock.patch('switchboard.dds_util.DDSUtil')
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

    @mock.patch('switchboard.dds_util.DDSUtil')
    def test_skips_populated_user(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        u = DukeDSUser.objects.create(dds_id='abcd-1234', full_name='Test User', email='test@example.com')
        self.assertTrue(u.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_user(u)
        self.assertTrue(u.populated())
        self.assertFalse(dds_util.get_remote_user.called)


    @mock.patch('switchboard.dds_util.DDSUtil')
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

    @mock.patch('switchboard.dds_util.DDSUtil')
    def test_skips_populated_project(self, mock_dds_util):
        setup_mock_ddsutil(mock_dds_util)
        p = DukeDSProject.objects.create(project_id='1234-defg', name='My project')
        self.assertTrue(p.populated())
        dds_util = mock_dds_util()
        m = ModelPopulator(dds_util)
        m.populate_project(p)
        self.assertTrue(p.populated())
        self.assertFalse(dds_util.get_remote_project.called)
