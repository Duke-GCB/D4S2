from switchboard.mailer import generate_message
from switchboard.dds_util import DeliveryDetails, DDSUtil


class Message(object):

    def __init__(self, message):
        self._message = message

    @property
    def email_text(self):
        """
        Returns the full text of the underlying email message
        :return: text of the message
        """
        return str(self._message.message())

    def send(self):
        """
        Sends underlying message
        """
        self._message.send()


class ShareMessage(Message):

    def __init__(self, share):
        """
        Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
        in a models.Share object. Then calls generate_message with email addresses, subject, and the details to
        generate an EmailMessage object, which can be .send()ed.
        """
        try:
            delivery_details = DeliveryDetails(share)
            sender = delivery_details.get_from_user()
            receiver = delivery_details.get_to_user()
            project = delivery_details.get_project()
            url = delivery_details.get_project_url()
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
        template_subject, template_body = delivery_details.get_share_template_text()
        context = {
            'project_name': project.name,
            'status': 'Draft',
            'recipient_name': receiver.full_name,
            'sender_name': sender.full_name,
            'sender_email': sender.email,
            'url': url,
            'signature': 'Duke Center for Genomic and Computational Biology\n'
                         'http://www.genome.duke.edu/cores-and-services/computational-solutions'
        }
        message = generate_message(sender.email, receiver.email, template_subject, template_body, context)
        super(ShareMessage, self).__init__(message)


class DeliveryMessage(Message):

    def __init__(self, delivery, accept_url):
        """
        Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
        in a models.Delivery object. Then calls generate_message with email addresses, subject, and the details to
        generate an EmailMessage object, which can be .send()ed.
        """

        try:
            delivery_details = DeliveryDetails(delivery)
            sender = delivery_details.get_from_user()
            receiver = delivery_details.get_to_user()
            project = delivery_details.get_project()
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
        template_subject, template_body = delivery_details.get_action_template_text('delivery')
        context = {
            'project_name': project.name,
            'status': 'Final',
            'recipient_name': receiver.full_name,
            'sender_name': sender.full_name,
            'sender_email': sender.email,
            'url': accept_url,
            'signature': 'Duke Center for Genomic and Computational Biology\n'
                         'http://www.genome.duke.edu/cores-and-services/computational-solutions'
        }
        message = generate_message(sender.email, receiver.email, template_subject, template_body, context)
        super(DeliveryMessage, self).__init__(message)


class ProcessedMessage(Message):

    def __init__(self, delivery, process_type, reason=''):
        """
        Generates an EmailMessage reporting whether or not the recipient accepted the delivery
        """
        try:
            delivery_details = DeliveryDetails(delivery)
            sender = delivery_details.get_from_user()
            receiver = delivery_details.get_to_user()
            project = delivery_details.get_project()
        except ValueError as e:
            raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
        template_subject, template_body = delivery_details.get_action_template_text(process_type)
        context = {
            'project_name': project.name,
            'recipient_name': receiver.full_name,
            'sender_name': sender.full_name,
            'type': process_type,
            'message': reason,
            'signature': 'Duke Center for Genomic and Computational Biology\n'
                         'http://www.genome.duke.edu/cores-and-services/computational-solutions'
        }
        message = generate_message(receiver.email, sender.email, template_subject, template_body, context)
        super(ProcessedMessage, self).__init__(message)


def perform_delivery(delivery):
    """
    Communicates with DukeDS via DDSUtil to add the to_user to a project
    :param delivery: A Delivery object
    :return:
    """
    auth_role = 'project_admin'
    try:
        # Add the to_user to the project, acting as the from_user
        ddsutil_from = DDSUtil(delivery.from_user.dds_id)
        ddsutil_from.add_user(delivery.to_user.dds_id, delivery.project.project_id, auth_role)
        # At this point, We'd like to remove the from_user from the project, changing ownership
        # However, we cannot remove the from_user if we are authenticated as that user
        # We experimented with authenticating as the to_user, but this was not practical
        # as we are not able to register our application to receive credentials from
        # the duke-authentication service. The alternative was to require all recipients
        # to obtain API keys and register them our service, but this is a poor user experience
        # We hope to simplify this if the from_user can remove himself/herself from the
        # project after he/she has added the to_user:
        # https://github.com/Duke-Translational-Bioinformatics/duke-data-service/issues/577

    except ValueError as e:
        raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
