from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist
from handover_api.models import Handover

MISSING_TOKEN_MSG = 'Missing authorization token.'
INVALID_TOKEN_MSG = 'Invalid authorization token.'
TOKEN_NOT_FOUND_MSG = 'Authorization token not found.'


def index(request):
    """
    Main accept screen where user accepts or rejects a project.
    """
    def render_accept(handover):
        return render(request, 'accept/index.html', {'token':  handover.token})
    return response_with_handover(request, render_accept)


def process(request):
    """
    Completes handover and redirects user to the project.
    """
    def redirect_view_project(handover):
        url = 'https://uatest.dataservice.duke.edu/portal/#/project/c949bd95-37bb-4da8-a214-0f2851b085c4'
        return redirect(url)
    return response_with_handover(request, redirect_view_project)


def response_with_handover(request, func):
    """
    Pull out token from request params and return func(token).
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
    else:
        return general_error(request, msg=MISSING_TOKEN_MSG, status=400)

def general_error(request, msg, status):
    message = msg
    context = {'message': message}
    return render(request, 'accept/error.html', context, status=status)

