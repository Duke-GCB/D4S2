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


class BaseMessage(object):
    def __init__(self, deliverable, user, accept_url=None, reason=None, process_type=None,
                 direction=MessageDirection.ToRecipient, warning_message=''):
        """
        Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
        in a models.Share or models.Delivery object. Then calls generate_message with email addresses, subject, and the details to
        generate an EmailMessage object, which can be .send()ed.
        """
        self.deliverable = deliverable
        try:
            delivery_details = self.make_delivery_details(self.deliverable, user)
            sender = delivery_details.get_from_user()
            receiver = delivery_details.get_to_user()
            context = delivery_details.get_email_context(accept_url, process_type, reason, warning_message)
            template_subject, template_body = self.get_templates(delivery_details)
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))

        # Delivery confirmation emails should go back to the delivery sender
        from_email, to_email = MessageDirection.email_addresses(sender, receiver, direction)
        self._message = generate_message(from_email, to_email, template_subject, template_body, context)

    def make_delivery_details(self, deliverable, user):
        raise NotImplementedError("Subclasses of Message should implement make_delivery_details.")

    def get_templates(self, delivery_details):
        return (None, None)

    @property
    def email_text(self):
        """
        Returns the full text of the underlying email message
        :return: text of the message
        """
        return str(self._message.message())

    @property
    def email_receipients(self):
        """
        Returns the recipients of the email message
        :return: list of email addresses to receive the message
        """
        return self._message.recipients()

    @property
    def email_from(self):
        """
        Returns the email sender's address
        :return: Email address from underlying message
        """
        return self._message.from_email

    def send(self):
        """
        Sends underlying message
        """
        self._message.send()


class BaseShareMessage(BaseMessage):

    def get_templates(self, delivery_details):
        return delivery_details.get_share_template_text()

    def __init__(self, share, user):
        """
        Generates a Message to the recipient informing they have access to a project
        :param share:
        """
        super(BaseShareMessage, self).__init__(share, user)


class BaseDeliveryMessage(BaseMessage):

    def get_templates(self, delivery_details):
        return delivery_details.get_action_template_text('delivery')

    def __init__(self, delivery, user, accept_url):
        """
        Generates a Message to the recipient prompting to accept the delivery
        """
        super(BaseDeliveryMessage, self).__init__(delivery, user, accept_url=accept_url)


class BaseProcessedMessage(BaseMessage):

    def get_templates(self, delivery_details):
        return delivery_details.get_action_template_text(self.process_type)

    def __init__(self, delivery, user, process_type, reason='', warning_message=''):
        """
        Generates a Message to the sender reporting whether or not the recipient accepted the delivery
        """
        self.process_type = process_type
        super(BaseProcessedMessage, self).__init__(delivery, user, process_type=process_type, reason=reason,
                                                   direction=MessageDirection.ToSender,
                                                   warning_message=warning_message)
