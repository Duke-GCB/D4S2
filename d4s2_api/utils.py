from switchboard.mailer import generate_message


class MessageDirection(object):
    ToRecipient = 0
    ToSender = 1

    @staticmethod
    def email_addresses(sender, receiver, direction=ToRecipient):
        if direction == MessageDirection.ToRecipient:
            return sender.email, receiver.email
        else:
            return receiver.email, sender.email


class Message(object):
    def __init__(self, from_email, to_email, template_subject, template_body, context):
        """
        :param from_email: str: email address of sender
        :param to_email: str: email address of recipient
        :param template_subject: str: subject of email
        :param template_body: str: template: django template
        :param context: dict: properties to be filled in on
        """
        self._message = generate_message(from_email, to_email, template_subject, template_body, context)

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

    def _make_message(self, email_template, accept_url=None, reason=None, process_type=None,
                      direction=MessageDirection.ToRecipient, warning_message=''):
        try:
            sender = self.delivery_details.get_from_user()
            receiver = self.delivery_details.get_to_user()
            context = self.delivery_details.get_email_context(accept_url, process_type, reason, warning_message)
            # Delivery confirmation emails should go back to the delivery sender
            from_email, to_email = MessageDirection.email_addresses(sender, receiver, direction)
            return Message(from_email, to_email, email_template.subject, email_template.body, context)
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information to build message: {}'.format(str(e)))
