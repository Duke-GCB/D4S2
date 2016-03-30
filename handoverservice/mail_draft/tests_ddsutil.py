from django.test import TestCase
from handover_api.models import User
from django.core.exceptions import ObjectDoesNotExist
import mock
import mail_draft
from mail_draft.dds_util import DDSUtil


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
        try:
            reload(mail_draft.dds_util)
        except NameError:
            # Python 3
            import importlib
            importlib.reload(mail_draft.dds_util)
        User.objects.create(dds_id=user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            ddsutil = DDSUtil(user_id)
            self.assertEqual(email, ddsutil.get_remote_user(user_id).email)
            self.assertTrue(instance.fetch_user.called)

    def testFailsWithoutAPIKeyUser(self):
        with self.settings(DDSCLIENT_PROPERTIES={}):
            self.assertEqual(len(User.objects.all()), 0)
            with self.assertRaises(ObjectDoesNotExist):
                ddsutil = DDSUtil('abcd-efgh-1234-5678')
                ddsutil.remote_store

