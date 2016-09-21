from django.core.mail import EmailMessage
from django.template import Template, Context
from django.utils.safestring import mark_safe


def generate_message(sender_email, rcpt_email, subject, template_text, context):
    # Mark the fields in context as safe, since we're not outputting HTML
    for k in context:
        context[k] = mark_safe(context[k])
    template = Template(template_text)
    message = template.render(Context(context))
    return EmailMessage(subject, message, sender_email, [rcpt_email])


