from django.test import TestCase, override_settings
from switchboard.mailer import generate_message

TEST_EMAIL_FROM_ADDRESS='noreply@domain.com'


@override_settings(EMAIL_FROM_ADDRESS=TEST_EMAIL_FROM_ADDRESS)
class MailerTestCase(TestCase):

    def setUp(self):
        self.reply_to_email = 'sender@domain.com'
        self.rcpt_email = 'receiver@school.edu'
        self.cc_email = 'core@domain.com'
        self.subject = 'Data is ready'
        self.template_text = 'order {{ order_number }} draft to {{ recipient_name }} from {{ sender_name }} for {{ project_name }}'
        self.context = {
            'order_number': 12345,
            'project_name': 'Project ABC',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
        }

    def test_generate_message(self):
        message = generate_message(self.reply_to_email, self.rcpt_email, self.cc_email, self.subject, self.template_text, self.context)
        self.assertIn('order 12345', message.body)
        self.assertIn('draft to Receiver Name', message.body)
        self.assertIn('from Sender Name', message.body)
        self.assertEqual(TEST_EMAIL_FROM_ADDRESS, message.from_email)
        self.assertIn(self.reply_to_email, message.reply_to)
        self.assertEqual(self.subject, message.subject)
        self.assertIn(self.rcpt_email, message.to)
        self.assertIn(self.cc_email, message.cc)

    def test_generate_message_no_cc(self):
        message = generate_message(self.reply_to_email, self.rcpt_email, None, self.subject, self.template_text, self.context)
        self.assertEqual(message.cc, [])

    def test_generate_message_no_escape(self):
        template_text = 'message {{ message }}'
        context = {
            'message': "I don't want this",
        }
        message = generate_message(self.reply_to_email, self.rcpt_email, self.cc_email, self.subject, template_text, context)
        self.assertIn("message I don't want this", message.body)
