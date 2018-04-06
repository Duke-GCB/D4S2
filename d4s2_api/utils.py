from switchboard.mailer import generate_message
from switchboard.dds_util import DeliveryDetails, DDSUtil
from d4s2_api.models import ShareRole, Share
from ddsc.core.ddsapi import DataServiceError


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

    def __init__(self, deliverable, user, accept_url=None, reason=None, process_type=None,
                 direction=MessageDirection.ToRecipient, warning_message=''):
        """
        Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
        in a models.Share or models.Delivery object. Then calls generate_message with email addresses, subject, and the details to
        generate an EmailMessage object, which can be .send()ed.
        """

        self.deliverable = deliverable
        try:
            delivery_details = DeliveryDetails(self.deliverable, user)
            sender = delivery_details.get_from_user()
            receiver = delivery_details.get_to_user()
            project = delivery_details.get_project()
            project_url = delivery_details.get_project_url()
            user_message = delivery_details.get_user_message()
            template_subject, template_body = self.get_templates(delivery_details)
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))

        context = {
            'project_name': project.name,
            'recipient_name': receiver.full_name,
            'recipient_email': receiver.email,
            'sender_email': sender.email,
            'sender_name': sender.full_name,
            'project_url': project_url,
            'accept_url': accept_url,
            'type': process_type,  # accept or decline
            'message': reason,  # decline reason
            'user_message': user_message,
            'warning_message': warning_message,
        }

        # Delivery confirmation emails should go back to the delivery sender
        from_email, to_email = MessageDirection.email_addresses(sender, receiver, direction)
        self._message = generate_message(from_email, to_email, template_subject, template_body, context)

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


class ShareMessage(Message):

    def get_templates(self, delivery_details):
        return delivery_details.get_share_template_text()

    def __init__(self, share, user):
        """
        Generates a Message to the recipient informing they have access to a project
        :param share:
        """
        super(ShareMessage, self).__init__(share, user)


class DeliveryMessage(Message):

    def get_templates(self, delivery_details):
        return delivery_details.get_action_template_text('delivery')

    def __init__(self, delivery, user, accept_url):
        """
        Generates a Message to the recipient prompting to accept the delivery
        """
        super(DeliveryMessage, self).__init__(delivery, user, accept_url=accept_url)


class ProcessedMessage(Message):

    def get_templates(self, delivery_details):
        return delivery_details.get_action_template_text(self.process_type)

    def __init__(self, delivery, user, process_type, reason='', warning_message=''):
        """
        Generates a Message to the sender reporting whether or not the recipient accepted the delivery
        """
        self.process_type = process_type
        super(ProcessedMessage, self).__init__(delivery, user, process_type=process_type, reason=reason,
                                               direction=MessageDirection.ToSender,
                                               warning_message=warning_message)


class DeliveryUtil(object):
    """
    Communicates with DukeDS via DDSUtil to accept the project transfer.
    Also gives download permission to the users in the delivery's share_to_users list.
    """
    def __init__(self, delivery, user, share_role, share_user_message):
        """
        :param delivery: A Delivery object
        :param user: The user with a DukeDS authentication credential
        :param share_role: str: share role to use for additional users
        :param share_user_message: str: reason for sharing to this user
        """
        self.delivery = delivery
        self.project_id = delivery.project_id
        self.user = user
        self.dds_util = DDSUtil(user)
        self.share_role = share_role
        self.share_user_message = share_user_message
        self.failed_share_users = []

    def accept_project_transfer(self):
        """
        Communicate with DukeDS via to accept the project transfer.
        """
        self.dds_util.accept_project_transfer(self.delivery.transfer_id)

    def share_with_additional_users(self):
        """
        Share project with additional users based on delivery share_to_users.
        Adds user names to failed_share_users for failed share commands.
        """
        for share_to_user in self.delivery.share_users.all():
            self._share_with_additional_user(share_to_user)

    def _share_with_additional_user(self, share_to_user):
        try:
            self.dds_util.share_project_with_user(self.project_id, share_to_user.dds_id, self.share_role)
            self._create_and_send_share_message(share_to_user)
        except DataServiceError:
            self.failed_share_users.append(self._try_lookup_user_name(share_to_user.dds_id))

    def _try_lookup_user_name(self, user_id):
        try:
            remote_user = self.dds_util.get_remote_user(user_id)
            return remote_user.full_name
        except DataServiceError:
            return user_id

    def _create_and_send_share_message(self, share_to_user):
        share = Share.objects.create(project_id=self.project_id,
                                     from_user_id=self.delivery.to_user_id,
                                     to_user_id=share_to_user.dds_id,
                                     role=self.share_role,
                                     user_message=self.share_user_message)
        message = ShareMessage(share, self.user)
        message.send()
        share.mark_notified(message.email_text)

    def get_warning_message(self):
        """
        Create message about any issues that occurred during share_with_additional_users.
        :return: str: end user warning message
        """
        failed_share_users_str = ', '.join(self.failed_share_users)
        warning_message = None
        if failed_share_users_str:
            warning_message = "Failed to share with the following user(s): " + failed_share_users_str
        return warning_message


def decline_delivery(delivery, user, reason):
    """
    Communicates with DukeDS via DDSUtil to add the to_user to a project
    :param user: The user with a DukeDS authentication credential
    :param delivery: A Delivery object
    :return:
    """
    try:
        dds_util = DDSUtil(user)
        dds_util.decline_project_transfer(delivery.transfer_id, reason)
    except ValueError as e:
        raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
