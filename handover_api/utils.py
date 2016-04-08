from switchboard.mailer import generate_message
from switchboard.dds_util import HandoverDetails

def send_draft(draft):
    """
    Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
    in a models.Draft object. Then calls generate_message with email addresses, subject, and the details to
    generate an EmailMessage object, which can be .send()ed.
    """

    try:
        handover_details = HandoverDetails(draft)
        sender = handover_details.get_from_user()
        receiver = handover_details.get_to_user()
        project = handover_details.get_project()
        data_url = handover_details.get_project_url()
    except ValueError as e:
        raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))
    template_name = 'draft.txt'
    subject = 'Data ready for Project {}'.format(project.name)
    context = {
        'project_name': project.name,
        'status': 'Draft',
        'recipient_name': receiver.full_name,
        'sender_name': sender.full_name,
        'sender_email': sender.email,
        'data_url': data_url,
        'signature': 'Duke Center for Genomic and Computational Biology\n'
                     'http://www.genome.duke.edu/cores-and-services/computational-solutions'
    }
    message = generate_message(sender.email, receiver.email, subject, template_name, context)
    message.send()
