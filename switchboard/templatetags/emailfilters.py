from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def strsplit(value, sep=None):
    return value.split(sep)

@register.filter
def listidx(value, idx=0):
    try:
        return value[idx]
    except IndexError:
        return ''
