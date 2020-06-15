from django.core.mail import EmailMessage
from django.template import Template, Context
from django.utils.safestring import mark_safe
from django.conf import settings

LOAD_EMAIL_FILTERS = '{% load emailfilters %}'


def template_with_email_filters(template_string):
    """
    Create a template that will load our email filters
    :param template_string: str
    :return: Template
    """
    return Template('{}{}'.format(LOAD_EMAIL_FILTERS, template_string))


def generate_message(reply_to_email, rcpt_email, cc_email, template_subject, template_body, context):
    # Mark the fields in context as safe, since we're not outputting HTML
    for k in context:
        context[k] = mark_safe(context[k])
    subject = template_with_email_filters(template_subject).render(Context(context))
    body = template_with_email_filters(template_body).render(Context(context))
    from_email = settings.EMAIL_FROM_ADDRESS
    cc_email_list = [cc_email] if cc_email else []
    return EmailMessage(subject, body, from_email, [rcpt_email], cc=cc_email_list, reply_to=[reply_to_email])
