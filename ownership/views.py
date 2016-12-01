from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from d4s2_api.models import Delivery, State
from d4s2_api.utils import perform_delivery, ProcessedMessage
from switchboard.dds_util import DeliveryDetails
from ddsc.core.ddsapi import DataServiceError
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required

MISSING_TOKEN_MSG = 'Missing authorization token.'
INVALID_TOKEN_MSG = 'Invalid authorization token.'
TOKEN_NOT_FOUND_MSG = 'Authorization token not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for declining this project.'


@login_required
@never_cache
def ownership_prompt(request):
    """
    Main accept screen where user accepts or declines a project.
    """
    return response_with_delivery(request, request.GET, render_accept_delivery_page)


def build_delivery_context(delivery):
    """
    Return dictionary of commonly needed delivery data for use with templates.
    """
    delivery_details = DeliveryDetails(delivery)
    from_user = delivery_details.get_from_user()
    to_user = delivery_details.get_to_user()
    project = delivery_details.get_project()
    return {
        'token': str(delivery.token),
        'from_name': from_user.full_name,
        'from_email': from_user.email,
        'to_name': to_user.full_name,
        'project_title': project.name,
    }


def render_accept_delivery_page(request, delivery):
    """
    Renders page with delivery details and ACCEPT/DECLINE buttons.
    """
    return render(request, 'ownership/index.html', build_delivery_context(delivery))


@login_required
@never_cache
def ownership_process(request):
    """
    Handles response to either accept or decline a project..
    """
    func = accept_project_redirect
    if request.POST.get('decline', None):
        func = render_decline_reason_prompt
    return response_with_delivery(request, request.POST, func)


def accept_project_redirect(request, delivery):
    """
    Perform delivery and redirect user to look at the project.
    """
    try:
        perform_delivery(user, delivery)
        message = ProcessedMessage(delivery, "accepted")
        message.send()
        delivery.mark_accepted(request.user.get_username(), message.email_text)
    except Exception as e:
        return general_error(request, msg=str(e), status=500)
    delivery_details = DeliveryDetails(delivery)
    url = delivery_details.get_project_url()
    return redirect(url)


def render_decline_reason_prompt(request, delivery):
    """
    Prompts for a reason for declineing the project.
    """
    return render(request, 'ownership/decline_reason.html', build_delivery_context(delivery))


def decline_project(request, delivery):
    """
    Marks delivery declined.
    """
    reason = request.POST.get('decline_reason')
    if not reason:
        context = build_delivery_context(delivery)
        context['error_message'] = REASON_REQUIRED_MSG
        return render(request, 'ownership/decline_reason.html', context, status=400)

    message = ProcessedMessage(delivery, "declined", "Reason: {}".format(reason))
    message.send()
    delivery.mark_declined(request.user.get_username(), reason, message.email_text)
    return render(request, 'ownership/decline_done.html', build_delivery_context(delivery))


@login_required
@never_cache
def ownership_decline(request):
    """
    Handle response from decline reason prompt.
    """
    if request.POST.get('cancel', None):
        url = url_with_token('ownership-prompt', request.POST.get('token'))
        return redirect(url)
    params = request.GET
    func = render_decline_reason_prompt
    if request.method == 'POST':
        params = request.POST
        func = decline_project
    return response_with_delivery(request, params, func)


def url_with_token(name, token=None):
    """
    Lookup url for name and append token to url.
    """
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def response_with_delivery(request, param_dict, func):
    """
    Pull out token from request params and return func(delivery).
    If delivery already complete render already complete message.
    Renders missing authorization token message otherwise.
    """
    token = param_dict.get('token', None)
    if token:
        try:
            delivery = Delivery.objects.get(token=token)
            if delivery.is_complete():
                return render_already_complete(request, delivery)
            return func(request, delivery)
        except ValueError as err:
            return general_error(request, msg=INVALID_TOKEN_MSG, status=400)
        except ObjectDoesNotExist:
            return general_error(request, msg=TOKEN_NOT_FOUND_MSG, status=404)
        except DataServiceError as err:
            return general_error(request, msg=(err), status=500)
    else:
        return general_error(request, msg=MISSING_TOKEN_MSG, status=400)


def render_already_complete(request, delivery):
    """
    User is trying to access a delivery that has already been declined or accepted.
    """
    status = State.DELIVERY_CHOICES[delivery.state][1]
    message = "This project has already been processed: {}.".format(status)
    return general_error(request, msg=message, status=400)


def general_error(request, msg, status):
    """
    Return the error template with the specified message and the status.
    """
    message = msg
    context = {'message': message}
    return render(request, 'ownership/error.html', context, status=status)

