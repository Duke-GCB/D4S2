from django.test import TestCase
from handover_api.models import User
from django.core.exceptions import ObjectDoesNotExist
import mock
from switchboard.dds_util import DDSUtil


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
        User.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
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
        User.objects.create(dds_id=self.user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(self.user_id)
            self.assertEqual(ddsutil.get_remote_project(project_id).name, project_name)
            self.assertTrue(instance.fetch_remote_project_by_id.called)

    def testFailsWithoutAPIKeyUser(self):
        with self.settings(DDSCLIENT_PROPERTIES={}):
            self.assertEqual(len(User.objects.all()), 0)
            with self.assertRaises(ObjectDoesNotExist):
                ddsutil = DDSUtil('abcd-efgh-1234-5678')
                ddsutil.remote_store

