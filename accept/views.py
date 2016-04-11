from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist
from handover_api.models import Handover
from handover_api.utils import perform_handover
from switchboard.dds_util import HandoverDetails
from ddsc.core.ddsapi import DataServiceError

MISSING_TOKEN_MSG = 'Missing authorization token.'
INVALID_TOKEN_MSG = 'Invalid authorization token.'
TOKEN_NOT_FOUND_MSG = 'Authorization token not found.'


def accept(request):
    """
    Main accept screen where user accepts or rejects a project.
    """
    def render_accept(handover):
        handover_details = HandoverDetails(handover)
        from_user = handover_details.get_from_user()
        to_user = handover_details.get_to_user()
        project = handover_details.get_project()
        context = {
            'token': str(handover.token),
            'from_name': from_user.full_name,
            'from_email': from_user.email,
            'to_name': to_user.full_name,
            'project_title': project.name,
        }
        return render(request, 'accept/index.html', context)
    return response_with_handover(request, render_accept)


def accept_process(request):
    """
    Completes handover and redirects user to the project.
    """
    def redirect_view_project(handover):
        try:
            perform_handover(handover)
        except Exception as e:
            return general_error(request, msg=str(e), status=500)
        handover.mark_accepted()
        handover_details = HandoverDetails(handover)
        url = handover_details.get_project_url()
        return redirect(url)
    return response_with_handover(request, redirect_view_project)


def response_with_handover(request, func):
    """
    Pull out token from request params and return func(handover).
    Renders missing authorization token message otherwise.
    """
    param_dict = request.POST
    if request.method == 'GET':
        param_dict = request.GET
    token = param_dict.get('token', None)
    if token:
        try:
            handover = Handover.objects.get(token=token)
            return func(handover)
        except ValueError:
            return general_error(request, msg=INVALID_TOKEN_MSG, status=400)
        except ObjectDoesNotExist:
            return general_error(request, msg=TOKEN_NOT_FOUND_MSG, status=404)
        except DataServiceError as err:
            return general_error(request, msg=(err), status=500)
    else:
        return general_error(request, msg=MISSING_TOKEN_MSG, status=400)


def general_error(request, msg, status):
    """
    Return the error template with the specified message and the status.
    """
    message = msg
    context = {'message': message}
    return render(request, 'accept/error.html', context, status=status)

