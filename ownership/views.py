from ddsc.core.ddsapi import DataServiceError
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render_to_response
from django.views.generic import TemplateView

from d4s2_api.models import DDSDelivery
from d4s2_api.models import State, ShareRole
from d4s2_api.utils import DeliveryUtil, decline_delivery, ProcessedMessage
from switchboard.dds_util import DeliveryDetails

MISSING_TRANSFER_ID_MSG = 'Missing transfer ID.'
INVALID_TRANSFER_ID = 'Invalid transfer ID.'
TRANSFER_ID_NOT_FOUND = 'Transfer ID not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for declining this project.'
SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'


class ResponseType:
    ERROR = -1
    TEMPLATE = 0
    REDIRECT = 1


class DeliveryViewBase(TemplateView):

    def handle_get(self):
        return None

    def handle_post(self):
        return None

    def _prepare(self, request):
        self.response_type = ResponseType.TEMPLATE
        self.request = request
        self.error_details = None
        self.redirect_target = None
        self.delivery = self.get_delivery()
        self.context = self.get_context_data()

    def _respond(self):
        if self.response_type == ResponseType.ERROR:
            return self.make_error_response()
        elif self.response_type == ResponseType.REDIRECT:
            return self.redirect(self.redirect_target)
        else:
            return self.render_to_response(self.context)


    def get(self, request):
        self._prepare(request)
        # If preparation failed, do not handle the request
        if not self.error_details:
            self.handle_get()
        return self._respond()

    def post(self, request):
        self._prepare(request)
        # If preparation failed, do not handle the request
        if not self.error_details:
            self.handle_post()
        return self._respond()

    def get_context_data(self, **kwargs):
        context = {}
        delivery = self.delivery
        if delivery:
            details = DeliveryDetails(delivery, self.request.user)
            from_user = details.get_from_user()
            to_user = details.get_to_user()
            project = details.get_project()
            project_url = details.get_project_url()
            context.update({
                'transfer_id': str(delivery.transfer_id),
                'from_name': from_user.full_name,
                'from_email': from_user.email,
                'to_name': to_user.full_name,
                'project_title': project.name,
                'project_url': project_url
            })
        return context

    def get_delivery(self):
        transfer_id = self.request.GET.get('transfer_id') or self.request.POST.get('transfer_id')
        if transfer_id:
            try:
                return DDSDelivery.objects.get(transfer_id=transfer_id)
            except DDSDelivery.DoesNotExist as e:
                self.set_error_details(404, TRANSFER_ID_NOT_FOUND)
        else:
            self.set_error_details(400, MISSING_TRANSFER_ID_MSG)
        return None

    # End DetailView overrides
    # Begin helper methods

    def set_redirect(self, target_view_name):
        self.response_type = ResponseType.REDIRECT
        self.redirect_target = target_view_name

    def set_error_details(self, status, message):
        self.response_type = ResponseType.ERROR
        self.error_details = {
            'status': status,
            'context': {'message': message},
        }

    def make_error_response(self):
        return render_to_response('ownership/error.html',
                                  status=self.error_details.get('status'),
                                  context=self.error_details.get('context'))

    def _get_query_string(self):
        delivery = self.delivery
        if delivery:
            return '?transfer_id={}'.format(delivery.transfer_id)
        else:
            return ''

    def redirect(self, view_name):
        return redirect(reverse(view_name) + self._get_query_string())

    def make_delivery_util(self):
        delivery = self.delivery
        request = self.request
        if delivery:
            return DeliveryUtil(delivery, request.user,
                                share_role=ShareRole.DOWNLOAD,
                                share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        else:
            return None

    # End helper methods
    # Begin Process actions

    def _set_already_complete_error(self):
        delivery = self.delivery
        status = State.DELIVERY_CHOICES[delivery.state][1]
        message = "This project has already been processed: {}.".format(status)
        self.set_error_details(400, message)

    def process_accept(self):
        delivery = self.delivery
        request = self.request
        if delivery.is_complete():
            self._set_already_complete_error()
            return
        try:
            delivery_util = self.make_delivery_util()
            delivery_util.accept_project_transfer()
            warning_message = delivery_util.get_warning_message()
            message = ProcessedMessage(delivery, request.user, 'accepted', warning_message=warning_message)
            message.send()
            delivery.mark_accepted(request.user.get_username(), message.email_text)
        except DataServiceError as e:
            self.set_error_details(500, 'Unable to transfer ownership: {}'.format(e.message))
        except Exception as e:
            self.set_error_details(500, str(e))

    def process_decline(self, reason):
        delivery = self.delivery
        request = self.request
        if delivery.is_complete():
            self._set_already_complete_error()
            return
        try:
            decline_delivery(delivery, request.user, reason)
            message = ProcessedMessage(delivery, request.user, 'declined', 'Reason: {}'.format(reason))
            message.send()
            delivery.mark_declined(request.user.get_username(), reason, message.email_text)
        except Exception as e:
            self.set_error_details(500, str(e))

    # End Process Actions


class PromptView(DeliveryViewBase):
    """
    Initial landing view, prompting for accept or decline button
    Posts to ProcessDeliveryView
    """
    http_method_names = ['get']
    template_name = 'ownership/index.html'


class ProcessView(DeliveryViewBase):
    """
    Handles POST from PromptView.
    If user clicked decline, redirects to the decline form.
    If clicked accept, process acceptance and redirect to accepted page
    """
    http_method_names = ['post']

    def handle_post(self):
        request = self.request
        if 'decline' in request.POST:
            # Redirect to decline page
            self.set_redirect('ownership-decline')
        else:
            # Cannot redirect to a POST, so we must process the acceptance here
            self.set_redirect('ownership-accepted')
            self.process_accept() # May override response type with an error


class DeclineView(DeliveryViewBase):
    """
    Handles GET to display form to prompt for reason
    When POSTed, process the decline action
    """
    http_method_names = ['get', 'post']
    template_name = 'ownership/decline_reason.html'

    # get() is not implemented, the base implementation renders the form with object and context

    def handle_post(self):
        request = self.request
        if 'cancel' in request.POST:
            # User canceled, redirect to prompt
            self.set_redirect('ownership-prompt')
        else:
            # User is declining the delivery
            reason = request.POST.get('decline_reason')
            if reason:
                self.set_redirect('ownership-declined')
                self.process_decline(reason) # May override response type with an error
            else:
                self.set_error_details(400, REASON_REQUIRED_MSG)


class AcceptedView(DeliveryViewBase):
    """
    Handles GET to show a message that the delivery was accepted
    """
    http_method_names = ['get']
    template_name = 'ownership/accepted.html'


class DeclinedView(DeliveryViewBase):
    """
    Handles GET to show a message that the delivery was declined
    """
    http_method_names = ['get']
    template_name = 'ownership/decline_done.html'
