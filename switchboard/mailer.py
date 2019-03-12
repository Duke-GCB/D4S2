from django.core.mail import EmailMessage
from django.template import Template, Context
from django.utils.safestring import mark_safe
from django.conf import settings


def generate_message(reply_to_email, rcpt_email, cc_email, template_subject, template_body, context):
    # Mark the fields in context as safe, since we're not outputting HTML
    for k in context:
        context[k] = mark_safe(context[k])
    subject = Template(template_subject).render(Context(context))
    body = Template(template_body).render(Context(context))
    from_email = settings.EMAIL_FROM_ADDRESS
    cc_email_list = [cc_email] if cc_email else []
    return EmailMessage(subject, body, from_email, [rcpt_email], cc=cc_email_list, reply_to=[reply_to_email])
