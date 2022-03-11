from ddsc.core.ddsapi import DataServiceError
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render_to_response
from django.views.generic import TemplateView
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
from d4s2_api.models import State
from switchboard.s3_util import S3Exception, S3DeliveryType, S3NotRecipientException
from switchboard.dds_util import DDSDeliveryType, DDSNotRecipientException
from switchboard.azure_util import AzDeliveryType, AzNotRecipientException, AzDestinationProjectAlreadyExists
from d4s2_api.utils import MessageDirection


MISSING_TRANSFER_ID_MSG = 'Missing transfer ID.'
TRANSFER_ID_NOT_FOUND = 'Transfer ID not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for declining this project.'
NOT_RECIPIENT_MSG = 'Unauthorized: Only the recipient can manage their deliveries.'


class ResponseType:
    ERROR = 'error'
    TEMPLATE = 'template'
    REDIRECT = 'redirect'


class DeliveryViewBase(TemplateView):

    def __init__(self, **kwargs):
        self.response_type = ResponseType.TEMPLATE
        self.delivery_type = None
        self.error_details = None
        self.redirect_target = None
        self.warning_message = None
        super(DeliveryViewBase, self).__init__(**kwargs)

    def handle_get(self):
        return

    def handle_post(self):
        return

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
        try:
            if delivery:
                details = self.delivery_type.make_delivery_details(delivery, self.request.user)
                context.update(details.get_context())
                context['delivery_type'] = self.delivery_type.name
            return context
        except (S3NotRecipientException, DDSNotRecipientException, AzNotRecipientException):
            self.set_error_details(403, NOT_RECIPIENT_MSG)

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
        elif delivery_type_name == AzDeliveryType.name:
            return AzDeliveryType
        else:
            return DDSDeliveryType

    def get_delivery(self):
        transfer_id = self._get_request_var('transfer_id')
        if transfer_id:
            try:
                return self.delivery_type.get_delivery(transfer_id=transfer_id)
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

    def set_already_complete_error(self):
        delivery = self.delivery
        status = State.DELIVERY_CHOICES[delivery.state][1]
        message = "This delivery has already been processed: {}.".format(status)
        self.set_error_details(400, message)

    def make_error_response(self):
        return render_to_response('ownership/error.html',
                                  status=self.error_details.get('status'),
                                  context=self.error_details.get('context'))

    def _get_query_string(self):
        query_dict = {}
        if self.delivery:
            query_dict['transfer_id'] = self.delivery.transfer_id
        if self.warning_message:
            query_dict['warning_message'] = self.warning_message
        query_dict['delivery_type'] = self.delivery_type.name
        return '?' + urlencode(query_dict)

    def make_redirect_response(self):
        return redirect(reverse(self.redirect_target) + self._get_query_string())

    def _action(self, request, handle_method):
        self._prepare(request)
        # If preparation failed, do not handle the request
        if not self.error_details:
            handle_method()
        return self._respond()

    # View handlers
    def get(self, request):
        return self._action(request, self.handle_get)

    def post(self, request):
        return self._action(request, self.handle_post)


class PromptView(DeliveryViewBase):
    """
    Initial landing view, prompting for accept or decline button
    Posts to ProcessDeliveryView
    """
    http_method_names = ['get']
    template_name = 'ownership/index.html'

    def handle_get(self):
        if self.delivery.is_complete():
            self.set_already_complete_error()


class ProcessView(DeliveryViewBase):
    """
    Handles POST from PromptView.
    If user clicked decline, redirects to the decline form.
    If clicked accept, process acceptance and redirect to accepted page
    """
    http_method_names = ['post']

    def process_accept(self):
        delivery = self.delivery
        request = self.request
        try:
            self.warning_message = self.delivery_type.transfer_delivery(delivery, request.user)
        except AzDestinationProjectAlreadyExists as dpae:
            self.set_error_details(400, str(dpae))
        except S3Exception as e:
            self.set_error_details(500, 'Unable to transfer s3 ownership: {}'.format(str(e)))
        except DataServiceError as e:
            self.set_error_details(500, 'Unable to transfer ownership: {}'.format(str(e)))
        except Exception as e:
            self.set_error_details(500, str(e))

    def handle_post(self):
        if self.delivery.is_complete():
            self.set_already_complete_error()
            return
        if 'decline' in self.request.POST:
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
        try:
            delivery_util = self.delivery_type.make_delivery_util(delivery, request.user)
            delivery_util.decline_delivery(reason)
            message = self.delivery_type.make_processed_message(delivery, request.user, 'declined',
                                                                MessageDirection.ToSender,
                                                                'Reason: {}'.format(reason))
            message.send()
            delivery.mark_declined(request.user.get_username(), reason, message.email_text)
        except Exception as e:
            self.set_error_details(500, str(e))

    def handle_get(self):
        if self.delivery.is_complete():
            self.set_already_complete_error()

    def handle_post(self):
        if self.delivery.is_complete():
            self.set_already_complete_error()
            return
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
