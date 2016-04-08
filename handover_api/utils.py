from switchboard.mailer import generate_message
from switchboard.dds_util import DDSUtil

def send_draft(draft):
    """
    Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
    in a models.Draft object. Then calls generate_message with email addresses, subject, and the details to
    generate an EmailMessage object, which can be .send()ed.
    """

    try:
        ddsutil = DDSUtil(draft.from_user_id)
        sender = ddsutil.get_remote_user(draft.from_user_id)
        receiver = ddsutil.get_remote_user(draft.to_user_id)
        project = ddsutil.get_remote_project(draft.project_id)
        url = ddsutil.get_project_url(draft.project_id)
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
        'url': url,
        'signature': 'Duke Center for Genomic and Computational Biology\n'
                     'http://www.genome.duke.edu/cores-and-services/computational-solutions'
    }
    message = generate_message(sender.email, receiver.email, subject, template_name, context)
    message.send()

def get_accept_url(handover):
    # TODO: lookup the accept url
    return 'https://itlab-1.gcb.duke.edu/accept?token=' + handover.token

def send_handover(handover):
    """
    Fetches user and project details from DukeDS (DDSUtil) based on user and project IDs recorded
    in a models.Handover object. Then calls generate_message with email addresses, subject, and the details to
    generate an EmailMessage object, which can be .send()ed.
    """

    try:
        ddsutil = DDSUtil(handover.from_user_id)
        sender = ddsutil.get_remote_user(handover.from_user_id)
        receiver = ddsutil.get_remote_user(handover.to_user_id)
        project = ddsutil.get_remote_project(handover.project_id)
    except ValueError as e:
        raise RuntimeError('Unable to retrieve information from DukeDS: {}'.format(e.message))

    template_name = 'handover.txt'
    subject = 'Data finalized for Project {}'.format(project.name)
    url = get_accept_url(handover)
    context = {
        'project_name': project.name,
        'status': 'Final',
        'recipient_name': receiver.full_name,
        'sender_name': sender.full_name,
        'sender_email': sender.email,
        'url': url,
        'signature': 'Duke Center for Genomic and Computational Biology\n'
                     'http://www.genome.duke.edu/cores-and-services/computational-solutions'
    }
    message = generate_message(sender.email, receiver.email, subject, template_name, context)
    message.send()
