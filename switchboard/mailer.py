from django.core.mail import EmailMessage
from django.template import Template, Context
from django.utils.safestring import mark_safe


def generate_message(sender_email, rcpt_email, template_subject, template_body, context):
    # Mark the fields in context as safe, since we're not outputting HTML
    for k in context:
        context[k] = mark_safe(context[k])
    subject = Template(template_subject).render(Context(context))
    body = Template(template_body).render(Context(context))
    return EmailMessage(subject, body, sender_email, [rcpt_email])


