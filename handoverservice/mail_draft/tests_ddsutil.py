from django.test import TestCase
from handover_api.models import User
import mock


class DDSUtilTestCase(TestCase):
    @mock.patch('ddsc.core.remotestore.RemoteStore')
    def testGetEmail(self, mockRemoteStore):
        user_id = 'abcd-1234-efgh-8876'
        email = 'example@domain.com'
        # Mock a remote user object, and bind it to fetch_user
        remote_user = mock.Mock()
        remote_user.email = email
        instance = mockRemoteStore.return_value
        instance.fetch_user.return_value = remote_user
        # Only import DDSUtil once we've patched RemoteStore
        from mail_draft.dds_util import DDSUtil
        User.objects.create(dds_id=user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            dds_util = DDSUtil(user_id)
            self.assertEqual(email, dds_util.get_email_address(user_id))
            self.assertTrue(instance.fetch_user.called)
