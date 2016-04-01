from mail_draft.mailer import generate_message
from mail_draft.dds_util import DDSUtil

def send_draft(draft):
    # Create a DDSUtil object with the sender's API key
    try:
        ddsutil = DDSUtil(draft.from_user_id)
        sender = ddsutil.get_remote_user(draft.from_user_id)
        receiver = ddsutil.get_remote_user(draft.to_user_id)
        project = ddsutil.get_remote_project(draft.project_id)
        data_url = ddsutil.get_project_url(draft.project_id)
    except ValueError as e:
        raise ValueError(e, message='Unable to retrieve information from DukeDS')
    template_name = 'draft.txt'
    subject = 'Data ready for Project {}'.format(project.name)
    context = {
        'project_name': project.name,
        'status': 'Draft',
        'recipient_name': receiver.full_name,
        'sender_name': sender.full_name,
        'sender_email': sender.email,
        'data_url': data_url,
        'signature': 'Duke Center for Genomic and Computational Biology\nInformatics\nhttp://www.genome.duke.edu/cores-and-services/computational-solutions'
    }
    message = generate_message(sender.email, receiver.email, subject, template_name, context)
    message.send()
