from django.test import TestCase
from mail_draft.mailer import generate_message
from mail_draft.dds_util import DDSUtil

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

    def testGetEmail(self):
        from handover_api.models import User

        # Requires user with an API key
        dds_id = 'abcd-1234-efgh-9696'
        User.objects.create(dds_id=dds_id, api_key='uhn3wk7h24ighg8i2')
        with self.settings(DDSCLIENT_PROPERTIES={}):
            dds_util = DDSUtil(dds_id)
            email_address = dds_util.get_email_address(dds_id)
            self.assertEqual(email_address, 'sender@domain.com')


