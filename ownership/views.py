from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from handover_api.models import Handover, State
from handover_api.utils import perform_handover, send_processed_mail
from switchboard.dds_util import HandoverDetails
from ddsc.core.ddsapi import DataServiceError
from django.views.decorators.cache import never_cache

MISSING_TOKEN_MSG = 'Missing authorization token.'
INVALID_TOKEN_MSG = 'Invalid authorization token.'
TOKEN_NOT_FOUND_MSG = 'Authorization token not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for rejecting this project.'


@never_cache
def ownership_prompt(request):
    """
    Main accept screen where user accepts or rejects a project.
    """
    return response_with_handover(request, request.GET, render_accept_handover_page)


def build_handover_context(handover):
    """
    Return dictionary of commonly needed handover data for use with templates.
    """
    handover_details = HandoverDetails(handover)
    from_user = handover_details.get_from_user()
    to_user = handover_details.get_to_user()
    project = handover_details.get_project()
    return {
        'token': str(handover.token),
        'from_name': from_user.full_name,
        'from_email': from_user.email,
        'to_name': to_user.full_name,
        'project_title': project.name,
    }


def render_accept_handover_page(request, handover):
    """
    Renders page with handover details and ACCEPT/REJECT buttons.
    """
    return render(request, 'ownership/index.html', build_handover_context(handover))


@never_cache
def ownership_process(request):
    """
    Handles response to either accept or reject a project..
    """
    func = accept_project_redirect
    if request.POST.get('reject', None):
        func = render_reject_reason_prompt
    return response_with_handover(request, request.POST, func)


def accept_project_redirect(request, handover):
    """
    Perform handover and redirect user to look at the project.
    """
    try:
        perform_handover(handover)
        # TODO: Include user
        handover.mark_accepted('user')
        send_processed_mail(handover, "accepted")
    except Exception as e:
        return general_error(request, msg=str(e), status=500)
    handover_details = HandoverDetails(handover)
    url = handover_details.get_project_url()
    return redirect(url)


def render_reject_reason_prompt(request, handover):
    """
    Prompts for a reason for rejecting the project.
    """
    return render(request, 'ownership/reject_reason.html', build_handover_context(handover))


def reject_project(request, handover):
    """
    Marks handover rejected.
    """
    reason = request.POST.get('reject_reason')
    if not reason:
        context = build_handover_context(handover)
        context['error_message'] = REASON_REQUIRED_MSG
        return render(request, 'ownership/reject_reason.html', context, status=400)

    # TODO: Include user
    handover.mark_rejected('user', reason)
    send_processed_mail(handover, "rejected", "Reason: {}".format(reason))

    return render(request, 'ownership/reject_done.html', build_handover_context(handover))


@never_cache
def ownership_reject(request):
    """
    Handle response from reject reason prompt.
    """
    if request.POST.get('cancel', None):
        url = url_with_token('ownership-prompt', request.POST.get('token'))
        return redirect(url)
    params = request.GET
    func = render_reject_reason_prompt
    if request.method == 'POST':
        params = request.POST
        func = reject_project
    return response_with_handover(request, params, func)


def url_with_token(name, token=None):
    """
    Lookup url for name and append token to url.
    """
    url = reverse(name)
    if token:
        url = "{}?token={}".format(url, token)
    return url


def response_with_handover(request, param_dict, func):
    """
    Pull out token from request params and return func(handover).
    If handover already complete render already complete message.
    Renders missing authorization token message otherwise.
    """
    token = param_dict.get('token', None)
    if token:
        try:
            handover = Handover.objects.get(token=token)
            if handover.is_complete():
                return render_already_complete(request, handover)
            return func(request, handover)
        except ValueError as err:
            return general_error(request, msg=INVALID_TOKEN_MSG, status=400)
        except ObjectDoesNotExist:
            return general_error(request, msg=TOKEN_NOT_FOUND_MSG, status=404)
        except DataServiceError as err:
            return general_error(request, msg=(err), status=500)
    else:
        return general_error(request, msg=MISSING_TOKEN_MSG, status=400)


def render_already_complete(request, handover):
    """
    Users is trying to access a handover that has already been rejected or accepted.
    """
    status = State.HANDOVER_CHOICES[handover.state][1]
    message = "This project has already been processed: {}.".format(status)
    return general_error(request, msg=message, status=400)


def general_error(request, msg, status):
    """
    Return the error template with the specified message and the status.
    """
    message = msg
    context = {'message': message}
    return render(request, 'ownership/error.html', context, status=status)

