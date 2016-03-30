from django.test import TestCase
from mail_draft.mailer import generate_message
from handover_api.models import User
import mock

class MailerTestCase(TestCase):

    def testGenerateMessage(self):
        sender_email = 'sender@domain.com'
        rcpt_email = 'receiver@school.edu'
        subject = 'Data is ready'
        template_name = 'draft.txt'
        context = {
            'order_number': 12345,
            'project_name': 'Project ABC',
            'status' : 'Draft',
            'contents' : '12 folders, 3 files',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
            'sender_email': sender_email,
            'data_url': 'http://domain.com/data',
            'signature': 'Sender Co\n123Fake St\nAnytown WA 90909',
        }
        message = generate_message(sender_email, rcpt_email, subject, template_name, context)
        self.assertIn('Sender Name has sent you a data set, which can be previewed at http://domain.com/data.', message.body)
        self.assertIn('Contents: 12 folders, 3 files', message.body)
        self.assertIn('please contact sender@domain.com', message.body)
        self.assertEqual(sender_email, message.from_email)
        self.assertIn(rcpt_email, message.to)


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
        from dds_util import DDSUtil
        User.objects.create(dds_id=user_id, api_key='uhn3wk7h24ighg8i2')
        # DDSUtil reads settings from django settings, so inject some here
        with self.settings(DDSCLIENT_PROPERTIES={}):
            dds_util = DDSUtil(user_id)
            self.assertEqual(email, dds_util.get_email_address(user_id))
