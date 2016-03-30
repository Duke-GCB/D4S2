from mail_draft.mailer import generate_message
from mail_draft.dds_util import DDSUtil

def send_draft(draft):
    # Create a DDSUtil object with the sender's API key
    try:
        ddsutil = DDSUtil(draft.from_user_id)
        sender = ddsutil.get_remote_user(draft.from_user_id)
        receiver = ddsutil.get_remote_user(draft.to_user_id)
    except ValueError as e:
        raise ValueError(e, message='Unable to retrieve email addresses from DukeDS')
    template_name = 'draft.txt'
    subject = "You've got data!"
    context = {
        'order_number': 12345,
        'project_name': 'Project ABC',
        'status': 'Draft',
        'contents': '12 folders, 3 files',
        'recipient_name': receiver.full_name,
        'sender_name': sender.full_name,
        'sender_email': sender.email,
        'data_url': 'http://domain.com/data',
        'signature': 'Sender Co\n123Fake St\nAnytown WA 90909',
    }
    message = generate_message(sender.email, receiver.email, subject, template_name, context)
    message.send()
