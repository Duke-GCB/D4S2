from django.test import TestCase
from switchboard.mailer import generate_message
from handover_api.models import DukeDSUser

class MailerTestCase(TestCase):

    def testGenerateMessage(self):
        sender_email = 'sender@domain.com'
        rcpt_email = 'receiver@school.edu'
        subject = 'Data is ready'
        template_name = 'draft.txt'
        context = {
            'order_number': 12345,
            'project_name': 'Project ABC',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
            'sender_email': sender_email,
            'url': 'http://domain.com/data',
            'signature': 'Sender Co\n123Fake St\nAnytown WA 90909',
        }
        message = generate_message(sender_email, rcpt_email, subject, template_name, context)
        self.assertIn('Sender Name has sent you a data set via the Duke Data Service', message.body)
        self.assertIn('contact sender@domain.com', message.body)
        self.assertIn('Preview URL: http://domain.com/data', message.body)
        self.assertEqual(sender_email, message.from_email)
        self.assertEqual(subject, message.subject)
        self.assertIn(rcpt_email, message.to)

    def testGenerateMessageNoEscape(self):
        sender_email = 'sender@domain.com'
        rcpt_email = 'receiver@school.edu'
        subject = 'Data is ready'
        template_name = 'processed.txt'
        context = {
            'project_name': 'Project ABC',
            'recipient_name': 'Receiver Name',
            'sender_name': 'Sender Name',
            'type': 'processed',
            'message': "I don't want this",
            'signature': 'Sender Co\n123Fake St\nAnytown WA 90909',
        }
        message = generate_message(sender_email, rcpt_email, subject, template_name, context)
        self.assertIn("I don't want this", message.body)
        self.assertEqual(sender_email, message.from_email)
        self.assertEqual(subject, message.subject)
        self.assertIn(rcpt_email, message.to)