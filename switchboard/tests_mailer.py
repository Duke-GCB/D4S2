from django.test import TestCase
from switchboard.mailer import generate_message


class MailerTestCase(TestCase):

    def testGenerateMessage(self):
        sender_email = 'sender@domain.com'
        rcpt_email = 'receiver@school.edu'
        subject = 'Data is ready'
        template_text = 'order {{ order_number }} draft to {{ recipient_name }} from {{ sender_name }} for {{ project_name }}'
        context = {
            'order_number': 12345,
            'project_name': 'Project ABC',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
        }
        message = generate_message(sender_email, rcpt_email, subject, template_text, context)
        self.assertIn('order 12345', message.body)
        self.assertIn('draft to Receiver Name', message.body)
        self.assertIn('from Sender Name', message.body)
        self.assertEqual(sender_email, message.from_email)
        self.assertEqual(subject, message.subject)
        self.assertIn(rcpt_email, message.to)

    def testGenerateMessageNoEscape(self):
        sender_email = 'sender@domain.com'
        rcpt_email = 'receiver@school.edu'
        subject = 'Data is ready'
        template_text = 'message {{ message }}'
        context = {
            'project_name': 'Project ABC',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
            'message': "I don't want this",
        }
        message = generate_message(sender_email, rcpt_email, subject, template_text, context)
        self.assertIn("message I don't want this", message.body)
        self.assertEqual(sender_email, message.from_email)
        self.assertEqual(subject, message.subject)
        self.assertIn(rcpt_email, message.to)
