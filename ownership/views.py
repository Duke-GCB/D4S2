from ddsc.core.ddsapi import DataServiceError
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render_to_response
from django.views.generic import TemplateView

from d4s2_api.models import DDSDelivery, S3Delivery
from d4s2_api.models import State, ShareRole
from d4s2_api.utils import DeliveryUtil, ProcessedMessage
from switchboard.s3_util import S3DeliveryDetails, S3DeliveryUtil, S3ProcessedMessage
from switchboard.dds_util import DeliveryDetails

MISSING_TRANSFER_ID_MSG = 'Missing transfer ID.'
INVALID_TRANSFER_ID = 'Invalid transfer ID.'
TRANSFER_ID_NOT_FOUND = 'Transfer ID not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for declining this project.'
SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'


class ResponseType:
    ERROR = 'error'
    TEMPLATE = 'template'
    REDIRECT = 'redirect'


class DDSDeliveryType:
    name = 'dds'
    delivery_cls = DDSDelivery
    delivery_util_cls = DeliveryUtil
    delivery_details_cls = DeliveryDetails
    processed_message_cls = ProcessedMessage


class S3DeliveryType:
    name = 's3'
    delivery_cls = S3Delivery
    delivery_util_cls = S3DeliveryUtil
    delivery_details_cls = S3DeliveryDetails
    processed_message_cls = S3ProcessedMessage


class DeliveryViewBase(TemplateView):

    def __init__(self, **kwargs):
        self.response_type = ResponseType.TEMPLATE
        self.delivery_type = None
        self.error_details = None
        self.redirect_target = None
        self.warning_message = None
        super(DeliveryViewBase, self).__init__(**kwargs)

    def handle_get(self):
        return None

    def handle_post(self):
        return None

    def _prepare(self, request):
        self.request = request
        self.delivery_type = self.get_delivery_type()
        self.delivery = self.get_delivery()
        self.context = self.get_context_data()

    def _respond(self):
        if self.response_type == ResponseType.ERROR:
            return self.make_error_response()
        elif self.response_type == ResponseType.REDIRECT:
            return self.make_redirect_response()
        else:
            return self.render_to_response(self.context)

    def get_context_data(self, **kwargs):
        context = {}
        delivery = self.delivery
        if delivery:
            details = self.delivery_type.delivery_details_cls(delivery, self.request.user)
            context.update(details.get_context())
            context['delivery_type'] = self.delivery_type.name
        return context

    def _get_request_var(self, key):
        return self.request.GET.get(key) or self.request.POST.get(key)

    def get_delivery_type(self):
        """
        Determine which DeliveryType adapter to use, based on 'delivery_type' GET/POST var.
        If not present, assume 'dds' and return a DDSDeliveryType

        :return:
        """
        delivery_type_name = self._get_request_var('delivery_type')
        if delivery_type_name == S3DeliveryType.name:
            return S3DeliveryType
        else:
            return DDSDeliveryType

    def get_delivery(self):
        transfer_id = self._get_request_var('transfer_id')
        if transfer_id:
            try:
                return self.delivery_type.delivery_cls.objects.get(transfer_id=transfer_id)
            except self.delivery_type.delivery_cls.DoesNotExist as e:
                self.set_error_details(404, TRANSFER_ID_NOT_FOUND)
        else:
            self.set_error_details(400, MISSING_TRANSFER_ID_MSG)
        return None

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
        from urllib import urlencode
        query_dict = {}
        if self.delivery:
            query_dict['transfer_id'] = self.delivery.transfer_id
        if self.warning_message:
            query_dict['warning_message'] = self.warning_message
        query_dict['delivery_type'] = self.delivery_type.name
        return '?' + urlencode(query_dict)

    def make_redirect_response(self):
        return redirect(reverse(self.redirect_target) + self._get_query_string())

    def make_delivery_util(self):
        delivery = self.delivery
        request = self.request
        if delivery:
            return self.delivery_type.delivery_util_cls(delivery, request.user,
                                                        share_role=ShareRole.DOWNLOAD,
                                                        share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        else:
            return None

    # View handlers
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
            delivery_util.share_with_additional_users()
            warning_message = delivery_util.get_warning_message()
            message = self.delivery_type.processed_message_cls(delivery, request.user, 'accepted', warning_message=warning_message)
            self.warning_message = warning_message
            message.send()
            delivery.mark_accepted(request.user.get_username(), message.email_text)
        except DataServiceError as e:
            self.set_error_details(500, 'Unable to transfer ownership: {}'.format(e.message))
        except Exception as e:
            self.set_error_details(500, str(e))

    def handle_post(self):
        request = self.request
        if 'decline' in request.POST:
            # Redirect to decline page
            self.set_redirect('ownership-decline')
        else:
            # Cannot redirect to a POST, so we must process the acceptance here
            self.set_redirect('ownership-accepted')
            self.process_accept()  # May override response type with an error


class DeclineView(DeliveryViewBase):
    """
    Handles GET to display form to prompt for reason
    When POSTed, process the decline action
    """
    http_method_names = ['get', 'post']
    template_name = 'ownership/decline_reason.html'

    def process_decline(self, reason):
        delivery = self.delivery
        request = self.request
        if delivery.is_complete():
            self._set_already_complete_error()
            return
        try:
            delivery_util = self.make_delivery_util()
            delivery_util.decline_delivery(reason)
            message = self.delivery_type.processed_message_cls(delivery, request.user, 'declined', 'Reason: {}'.format(reason))
            message.send()
            delivery.mark_declined(request.user.get_username(), reason, message.email_text)
        except Exception as e:
            self.set_error_details(500, str(e))

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
                self.process_decline(reason)  # May override response type with an error
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
