from django.views.generic import DetailView
from django.shortcuts import redirect
from d4s2_api.models import DDSDelivery, S3Delivery
from d4s2_api.models import State, ShareRole
from d4s2_api.utils import DeliveryDetails
from django.core.urlresolvers import reverse
from d4s2_api.utils import DeliveryUtil, decline_delivery, ProcessedMessage
from switchboard.dds_util import DeliveryDetails
from ddsc.core.ddsapi import DataServiceError
from django.http import Http404


MISSING_TRANSFER_ID_MSG = 'Missing transfer ID.'
INVALID_TRANSFER_ID = 'Invalid transfer ID.'
TRANSFER_ID_NOT_FOUND = 'Transfer ID not found.'
REASON_REQUIRED_MSG = 'You must specify a reason for declining this project.'
SHARE_IN_RESPONSE_TO_DELIVERY_MSG = 'Shared in response to project delivery.'


class DeliveryViewBase(DetailView):

    def make_delivery_util(self, request):
        delivery = self.get_object()
        delivery_util = DeliveryUtil(delivery, request.user,
                                     share_role=ShareRole.DOWNLOAD,
                                     share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        return delivery_util

    def get_context_data(self, **kwargs):
        context = super(DeliveryViewBase, self).get_context_data(**kwargs)
        delivery = self.object
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

    def get_object(self, queryset=None):
        transfer_id = self.request.GET.get('transfer_id') or self.request.POST.get('transfer_id')
        try:
            return DDSDelivery.objects.get(transfer_id=transfer_id)
        except DDSDelivery.DoesNotExist as e:
            raise Http404(e)

    def _get_query_string(self):
        delivery = self.get_object()
        return 'transfer_id={}'.format(delivery.transfer_id)

    def process_accept(self):
        print('Process Acceptance of Delivery..')

    def process_decline(self):
        print('Process Decline of delivery')

    def redirect(self, view_name):
        return redirect(reverse(view_name) + '?' + self._get_query_string())


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
    http_method_names =  ['post']

    def post(self, request):
        if 'decline' in request.POST:
            # Redirect to decline page
            return self.redirect('ownership-decline')
        else:
            # Cannot redirect to a POST, so we must process the acceptance here
            self.process_accept()
            return self.redirect('ownership-accepted')


class DeclineView(DeliveryViewBase):
    """
    Handles GET to display form to prompt for reason
    When POSTed, process the decline action
    """
    http_method_names = ['get','post']
    template_name = 'ownership/decline_reason.html'
    # get() is not implemented, the base implementation renders the form with object and context

    def post(self, request):
        if 'cancel' in request.POST:
            # User canceled, redirect to prompt
            return self.redirect('ownership-prompt')
        else:
            # User is declining the delivery
            self.process_decline()
            return self.redirect('ownership-declined')


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

