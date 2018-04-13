from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from d4s2_api.models import Delivery, State, ShareRole, S3Delivery
from d4s2_api.utils import DeliveryUtil, decline_delivery, S3ProcessedMessage
from switchboard.s3_util import S3DeliveryDetails, S3DeliveryUtil
from ddsc.core.ddsapi import DataServiceError
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from ownership.views import MISSING_TRANSFER_ID_MSG, INVALID_TRANSFER_ID, TRANSFER_ID_NOT_FOUND, \
    REASON_REQUIRED_MSG, SHARE_IN_RESPONSE_TO_DELIVERY_MSG
from background_task import background


@login_required
@never_cache
def ownership_prompt(request):
    """
    Main accept screen where user accepts or declines a project.
    """
    return response_with_delivery(request, request.GET, render_accept_delivery_page)


def build_delivery_context(s3_delivery, user):
    """
    Return dictionary of commonly needed delivery data for use with templates.
    """
    delivery_details = S3DeliveryDetails(s3_delivery, user=user)
    return delivery_details.get_context()


def render_accept_delivery_page(request, delivery):
    """
    Renders page with delivery details and ACCEPT/DECLINE buttons.
    """
    return render(request, 's3ownership/index.html', build_delivery_context(delivery, request.user))


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


def accept_project_redirect(request, s3_delivery):
    """
    Accept delivery and redirect user to look at the project.
    """
    try:
        deliver_project_and_send_emails(request.user.id, s3_delivery.id)
    except Exception as e:
        return general_error(request, msg=str(e), status=500)
    return redirect(reverse('s3ownership-accepted') + '?s3_delivery_id=' + str(s3_delivery.id))


@background
def deliver_project_and_send_emails(user_id, s3_delivery_id):
    """
    In background deliver a project to the specified user.
    :param user_id:
    :param s3_delivery_id:
    """
    user = User.objects.get(pk=user_id)
    s3_delivery = S3Delivery.objects.get(pk=s3_delivery_id)
    delivery_util = S3DeliveryUtil(s3_delivery, user)
    delivery_util.accept_project_transfer()
    message = S3ProcessedMessage(s3_delivery, user, "accepted")
    message.send()
    s3_delivery.mark_accepted(user.get_username(), message.email_text)


def render_decline_reason_prompt(request, delivery):
    """
    Prompts for a reason for declineing the project.
    """
    return render(request, 's3ownership/decline_reason.html', build_delivery_context(delivery, request.user))


def decline_project(request, s3_delivery):
    """
    Marks delivery declined.
    """
    reason = request.POST.get('decline_reason')
    if not reason:
        context = build_delivery_context(s3_delivery, request.user)
        context['error_message'] = REASON_REQUIRED_MSG
        return render(request, 's3ownership/decline_reason.html', context, status=400)
    try:
        delivery_util = S3DeliveryUtil(s3_delivery, request.user)
        delivery_util.decline_delivery()
        message = S3ProcessedMessage(s3_delivery, request.user, "declined", "Reason: {}".format(reason))
        message.send()
        s3_delivery.mark_declined(request.user.get_username(), reason, message.email_text)
        return render(request, 's3ownership/decline_done.html', build_delivery_context(s3_delivery, request.user))
    except Exception as e:
        return general_error(request, msg=str(e), status=500)


@login_required
@never_cache
def ownership_decline(request):
    """
    Handle response from decline reason prompt.
    """
    if request.POST.get('cancel', None):
        url = url_with_s3_delivery_id('s3ownership-prompt', request.POST.get('s3_delivery_id'))
        return redirect(url)
    params = request.GET
    func = render_decline_reason_prompt
    if request.method == 'POST':
        params = request.POST
        func = decline_project
    return response_with_delivery(request, params, func)


def url_with_s3_delivery_id(name, s3_delivery_id=None):
    """
    Lookup url for name and append transfer_id to url.
    """
    url = reverse(name)
    if s3_delivery_id:
        url = "{}?s3_delivery_id={}".format(url, s3_delivery_id)
    return url


def response_with_delivery(request, param_dict, func):
    """
    Pull out transfer_id from request params and return func(delivery).
    If delivery already complete render already complete message.
    Renders missing authorization transfer_id message otherwise.
    """
    s3_delivery_id = param_dict.get('s3_delivery_id', None)
    if s3_delivery_id:
        try:
            details = S3DeliveryDetails.from_s3_delivery_id(s3_delivery_id, request.user)
            delivery = details.get_delivery()
            # update the status
            if delivery.is_complete():
                return render_already_complete(request, delivery)
            return func(request, delivery)
        except ObjectDoesNotExist:
            return general_error(request, msg=TRANSFER_ID_NOT_FOUND, status=404)
        except DataServiceError as err:
            return general_error(request, msg=(err), status=500)
    else:
        return general_error(request, msg=MISSING_TRANSFER_ID_MSG, status=400)


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
    return render(request, 's3ownership/error.html', context, status=status)


def ownership_accepted(request):
    """
    Shows an acceptance page, with link to the Data Service Project
    """
    try:
        s3_delivery_id = request.GET.get('s3_delivery_id', None)
        warning_message = request.GET.get('warning_message', None)
        delivery = S3DeliveryDetails.from_s3_delivery_id(s3_delivery_id, request.user).get_delivery()
        context = build_delivery_context(delivery, request.user)
        context['warning_message'] = warning_message
        return render(request, 's3ownership/accepted.html', context)
    except ObjectDoesNotExist:
        return general_error(request, msg=TRANSFER_ID_NOT_FOUND, status=404)
