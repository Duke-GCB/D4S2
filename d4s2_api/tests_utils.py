from mock import patch, Mock, MagicMock, call, create_autospec
from django.test import TestCase
from d4s2_api.utils import MessageDirection, Message, MessageFactory, get_netid_from_user
from switchboard.dds_util import DeliveryDetails, StorageTypes


class MessageDirectionTestCase(TestCase):

    def setUp(self):
        self.sender_email = 'sender@email.com'
        self.receiver_email = 'receiver@email.com'

    def test_default_order(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender_email, self.receiver_email)
        self.assertEqual(ordered_addresses, (self.sender_email, self.receiver_email))

    def test_orders_forward(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender_email, self.receiver_email, MessageDirection.ToRecipient)
        self.assertEqual(ordered_addresses, (self.sender_email, self.receiver_email))

    def test_orders_reverse(self):
        ordered_addresses = MessageDirection.email_addresses(self.sender_email, self.receiver_email, MessageDirection.ToSender)
        self.assertEqual(ordered_addresses, (self.receiver_email, self.sender_email))


class MessageTestCase(TestCase):

    def test_email_text(self):
        message = Message(reply_to_email='bob@bob.com', rcpt_email='joe@joe.com', template_subject='Hello',
                          template_body='Details for you {{value}}', context={'value':"123"}, cc_email='cc@cc.com')
        self.assertIn('Reply-To: bob@bob.com', message.email_text)
        self.assertIn('To: joe@joe.com', message.email_text)
        self.assertIn('Cc: cc@cc.com', message.email_text)
        self.assertIn('Subject: Hello', message.email_text)
        self.assertIn('Details for you 123', message.email_text)

    @patch('d4s2_api.utils.generate_message', autospec=True)
    def test_send(self, mock_generate_message):
        message = Message(reply_to_email='bob@bob.com', rcpt_email='joe@joe.com', template_subject='Hello',
                          template_body='Details for you {{value}}', context={'value':"123"})
        message.send()
        self.assertTrue(mock_generate_message.return_value.send.called)
        self.assertEqual(mock_generate_message.call_args, call('bob@bob.com', 'joe@joe.com', None, 'Hello',
                                                               'Details for you {{value}}', {'value': '123'}))


class MessageFactoryTestCase(TestCase):

    def setUp(self):
        self.delivery_details = create_autospec(DeliveryDetails)
        self.delivery_details.storage = 'dds'
        self.email_template_set = Mock()
        self.delivery_details.email_template_set = self.email_template_set
        self.email_template_set.template_for_name.return_value = Mock(subject='subject', body='body')
        self.email_template_set.reply_address = None
        self.email_template_set.cc_address = None
        self.delivery_details.get_from_user.return_value = Mock(email='bob@bob.com')
        self.delivery_details.get_to_user.return_value = Mock(email='joe@joe.com')
        self.delivery_details.get_email_context.return_value = {}
        self.delivery_details.delivery = Mock()

    @patch('d4s2_api.utils.Message', autospec=True)
    def test_make_share_message(self, mock_message):
        factory = MessageFactory(self.delivery_details, None)
        factory.make_share_message()
        self.assertEqual(mock_message.call_args, call('bob@bob.com', 'joe@joe.com', 'subject', 'body', {}, None))
        self.assert_template_for_name_call(self.delivery_details.delivery.email_template_name.return_value)

    @patch('d4s2_api.utils.Message', autospec=True)
    def test_make_delivery_message(self, mock_message):
        factory = MessageFactory(self.delivery_details, None)
        factory.make_delivery_message(accept_url='accept url')
        self.assertEqual(mock_message.call_args, call('bob@bob.com', 'joe@joe.com', 'subject', 'body', {}, None))
        self.assert_template_for_name_call('delivery')

    @patch('d4s2_api.utils.Message', autospec=True)
    def test_make_processed_message_to_sender(self, mock_message):
        factory = MessageFactory(self.delivery_details, None)
        factory.make_processed_message('accepted', MessageDirection.ToSender, warning_message='warning details')
        self.assertEqual(mock_message.call_args,
                         call('joe@joe.com', 'bob@bob.com', 'subject', 'body', {}, None))
        self.assertEqual(self.delivery_details.get_email_context.call_args,
                         call(None, 'accepted', '', 'warning details'))
        self.assert_template_for_name_call('accepted')

    @patch('d4s2_api.utils.Message', autospec=True)
    def test_make_processed_message_to_recipient(self, mock_message):
        factory = MessageFactory(self.delivery_details, None)
        factory.make_processed_message('accepted_recipient', MessageDirection.ToRecipient,
                                       warning_message='warning details')
        self.assertEqual(mock_message.call_args, call('bob@bob.com', 'joe@joe.com', 'subject', 'body', {}, None))
        self.assertEqual(self.delivery_details.get_email_context.call_args,
                         call(None, 'accepted_recipient', '', 'warning details'))
        self.assert_template_for_name_call('accepted_recipient')

    @patch('d4s2_api.utils.Message', autospec=True)
    def test_make_canceled_message(self, mock_message):
        factory = MessageFactory(self.delivery_details, None)
        factory.make_canceled_message()
        self.assertEqual(mock_message.call_args, call('bob@bob.com', 'joe@joe.com', 'subject', 'body', {}, None))
        self.assert_template_for_name_call('delivery_canceled')

    def assert_template_for_name_call(self, arg):
        self.assertEqual(self.email_template_set.template_for_name.call_args, call(arg))

    @patch('d4s2_api.utils.UserEmailTemplateSet')
    def test_get_reply_to_address_uses_template_set(self, mock_use_email_template_set):
        mock_user = Mock()
        delivery_details = create_autospec(DeliveryDetails)
        delivery_details.storage = 'dds'
        delivery_details.email_template_set = Mock()
        mock_use_email_template_set.user_is_setup.return_value = True
        mock_email_template_set = Mock(reply_address='reply@email.com')
        mock_use_email_template_set.objects.get.return_value.email_template_set = mock_email_template_set
        factory = MessageFactory(delivery_details, mock_user)
        sender = Mock(email='sender@email.com')
        reply_to_address = factory.get_reply_to_address(sender)
        self.assertEqual(reply_to_address, 'reply@email.com')

    def test_get_reply_to_address_falls_back_to_sender(self):
        delivery_details = create_autospec(DeliveryDetails)
        delivery_details.storage = 'dds'
        delivery_details.email_template_set = Mock()
        factory = MessageFactory(delivery_details, None)
        sender = Mock(email='sender@email.com')
        reply_to_address = factory.get_reply_to_address(sender)
        self.assertEqual(reply_to_address, 'sender@email.com')

    def test_get_cc_address_uses_template_set(self):
        delivery_details = create_autospec(DeliveryDetails)
        delivery_details.storage = 'dds'
        delivery_details.email_template_set = Mock(cc_address='cc@email.com')
        factory = MessageFactory(delivery_details, None)
        cc_address = factory.get_cc_address()
        self.assertEqual(cc_address, 'cc@email.com')

    def test_get_cc_address_falls_back_to_none(self):
        delivery_details = create_autospec(DeliveryDetails)
        delivery_details.email_template_set = Mock(cc_address=None)
        factory = MessageFactory(delivery_details, None)
        cc_address = factory.get_cc_address()
        self.assertIsNone(cc_address)

    @patch('d4s2_api.utils.UserEmailTemplateSet')
    def test_get_reply_to_address(self, mock_user_email_template_set):
        mock_user_email_template_set.user_is_setup.return_value = False
        mock_user_email_template_set.objects.get.return_value = Mock(
            email_template_set=Mock(reply_address="important@email.com")
        )
        delivery_details = create_autospec(DeliveryDetails)
        delivery_details.storage = StorageTypes.DDS
        delivery_details.email_template_set = Mock(cc_address=None)
        factory = MessageFactory(delivery_details, None)
        self.assertEqual(factory.get_reply_to_address(Mock(email='test@email.com')), 'test@email.com')
        mock_user_email_template_set.user_is_setup.return_value = True
        self.assertEqual(factory.get_reply_to_address(Mock(email='test@email.com')), 'important@email.com')


class TestFuncs(TestCase):
    def test_get_netid_from_user(self):
        self.assertEqual(get_netid_from_user(user=Mock(username='joe')), 'joe')
        self.assertEqual(get_netid_from_user(user=Mock(username='joe@email.com')), 'joe')
