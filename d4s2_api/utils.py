from switchboard.mailer import generate_message
from switchboard.dds_util import DeliveryDetails, DDSUtil
from models import ShareRole, Share, DukeDSUser
from ddsc.core.ddsapi import DataServiceError

SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'


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
                 direction=MessageDirection.ToRecipient):
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
            'type': process_type, # accept or decline
            'message': reason, # decline reason
            'user_message': user_message,
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

    def __init__(self, delivery, user, process_type, reason=''):
        """
        Generates a Message to the sender reporting whether or not the recipient accepted the delivery
        """
        self.process_type = process_type
        super(ProcessedMessage, self).__init__(delivery, user, process_type=process_type, reason=reason,
                                               direction=MessageDirection.ToSender)


def accept_delivery(delivery, user):
    """
    Communicates with DukeDS via DDSUtil to accept the project transfer.
    Also gives download permission to the users in the delivery's share_to_users list.
    :param user: The user with a DukeDS authentication credential
    :param delivery: A Delivery object
    """
    try:
        delivery_util = DeliveryUtil(delivery, user,
                                     share_role=ShareRole.DOWNLOAD,
                                     share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        delivery_util.accept_project_transfer()
        delivery_util.share_with_additional_users()
        return delivery_util.failed_shares
    except DataServiceError as e:
        raise RuntimeError('Unable to transfer ownership: {}'.format(e.message))


class DeliveryUtil(object):
    """
    Wraps up accepting a delivery and sharing project with additional users
    """
    def __init__(self, delivery, user, share_role, share_user_message):
        self.delivery = delivery
        self.project = delivery.project
        self.user = user
        self.dds_util = DDSUtil(user)
        self.share_role = share_role
        self.share_user_message = share_user_message
        self.failed_shares = []

    def accept_project_transfer(self):
        self.dds_util.accept_project_transfer(self.delivery.transfer_id)

    def share_with_additional_users(self):
        for share_to_user in self.delivery.share_to_users.all():
            self._share_with_additional_user(share_to_user)

    def _share_with_additional_user(self, share_to_user):
        try:
            self.dds_util.share_project_with_user(self.project.project_id, share_to_user.dds_id, self.share_role)
            self._create_and_send_share_message(share_to_user)
        except DataServiceError as dse:
            self.failed_shares.append(dse)

    def _create_and_send_share_message(self, share_to_user):
        share = Share.objects.create(project=self.project,
                                     from_user=self.delivery.to_user,
                                     to_user=share_to_user,
                                     role=self.share_role,
                                     user_message=self.share_user_message)
        message = ShareMessage(share, self.user)
        message.send()
        share.mark_notified(message.email_text)


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
