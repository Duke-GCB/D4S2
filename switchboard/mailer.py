from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


def generate_message(sender_email, rcpt_email, subject, template_name, context):
    # Mark the fields in context as safe, since we're not outputting HTML
    for k in context:
        context[k] = mark_safe(context[k])
    message = render_to_string(template_name, context)
    return EmailMessage(subject, message, sender_email, [rcpt_email])


