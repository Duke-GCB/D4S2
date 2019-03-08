from switchboard.mailer import generate_message


class MessageDirection(object):
    ToRecipient = 0
    ToSender = 1

    @staticmethod
    def email_addresses(sender_email, receiver_email, direction=ToRecipient):
        """
        Return a tuple of (reply_to_email, rcpt_email), from a delivery sender/receiver
        :param sender: user object of the delivery creator with an .email property to extract
        :param receiver: user object of the delivery recipient with an .email property to extract
        :param direction: One of the enumerated values above
        :return: tuple of (reply_to_email, rcpt_email)
        """
        if direction == MessageDirection.ToRecipient:
            return sender_email, receiver_email
        else:
            return receiver_email, sender_email


class Message(object):

    def __init__(self, reply_to_email, rcpt_email, template_subject, template_body, context, cc_email=None):
        """
        :param reply_to_email: str: email address to use for reply-to
        :param rcpt_email: str: email address of recipient
        :param template_subject: str: subject of email
        :param template_body: str: template: django template
        :param context: dict: properties to be filled in on
        :param cc_email: str: email address to cc (may be None)
        """
        self._message = generate_message(reply_to_email, rcpt_email, cc_email, template_subject, template_body, context)

    @property
    def email_text(self):
        """
        Returns the full text of the underlying email message
        :return: text of the message
        """
        return str(self._message.message())

    def send(self):
        self._message.send()


class MessageFactory(object):

    def __init__(self, delivery_details):
        self.delivery_details = delivery_details
        self.email_template_set = delivery_details.email_template_set

    def make_share_message(self):
        # This method is only applicable if the internal delivery is a share type
        share = self.delivery_details.delivery
        email_template = self.email_template_set.template_for_name(share.email_template_name())
        return self._make_message(email_template)

    def make_delivery_message(self, accept_url):
        email_template = self.email_template_set.template_for_name('delivery')
        return self._make_message(email_template, accept_url=accept_url)

    def make_processed_message(self, process_type, direction, warning_message=''):
        email_template = self.email_template_set.template_for_name(process_type)
        return self._make_message(email_template, reason='',
                                  process_type=process_type,
                                  direction=direction,
                                  warning_message=warning_message)

    def make_canceled_message(self):
        email_template = self.email_template_set.template_for_name('delivery_canceled')
        return self._make_message(email_template)

    def get_reply_to_address(self, sender):
        if self.email_template_set.reply_address:
            return self.email_template_set.reply_address
        else:
            return sender.email

    def get_cc_address(self):
        if self.email_template_set.cc_address:
            return self.email_template_set.cc_address
        else:
            return None

    def _make_message(self, email_template, accept_url=None, reason=None, process_type=None,
                      direction=MessageDirection.ToRecipient, warning_message=''):
        try:
            delivery_from_user = self.delivery_details.get_from_user()
            delivery_to_user = self.delivery_details.get_to_user()
            context = self.delivery_details.get_email_context(accept_url, process_type, reason, warning_message)

            # Get the email addresses to use for the creator and recipient of the delivery
            delivery_from_user_email = self.get_reply_to_address(delivery_from_user)
            delivery_cc_email = self.get_cc_address()
            delivery_to_user_email = delivery_to_user.email

            # Based on the type of message (delivery, confirmation), determine the direction of the addresses
            reply_to_email, rcpt_email = MessageDirection.email_addresses(delivery_from_user_email, delivery_to_user_email, direction)
            return Message(reply_to_email, rcpt_email, email_template.subject, email_template.body, context, delivery_cc_email)

        except ValueError as e:
            raise RuntimeError('Unable to retrieve information to build message: {}'.format(str(e)))
