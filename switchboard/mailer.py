from django.core.mail import EmailMessage
from django.template.loader import render_to_string, get_template


def generate_message(sender_email, rcpt_email, subject, template_name, context):
    message = render_to_string(template_name, context)
    return EmailMessage(subject, message, sender_email, [rcpt_email])


