from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from d4s2_api.models import DDSDelivery, Share, State, UserEmailTemplateSet, EmailTemplateSet
from d4s2_api_v1.serializers import DeliverySerializer, ShareSerializer
from switchboard.dds_util import DDSUtil, DDSMessageFactory
from django.core.urlresolvers import reverse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
EMAIL_TEMPLATES_NOT_SETUP_MSG = """Email templates need to be setup for your account.
Please contact gcb-help@duke.edu."""
CANNOT_PASS_EMAIL_TEMPLATE_SET = """You cannot create this item by passing email_template_set, 
these are determined by user email template setup."""
ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG = """Email templates need to be setup for this item.
Please contact gcb-help@duke.edu."""


def build_accept_url(request, transfer_id, delivery_type):
    query_dict = {
        'transfer_id': transfer_id,
        'delivery_type': delivery_type
    }
    accept_path = reverse('ownership-prompt') + '?transfer_id={}&delivery_type={}'.format(transfer_id, delivery_type)
    accept_url = request.build_absolute_uri(accept_path)
    return accept_url


class AlreadyNotifiedException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Already notified'


class ModelWithEmailTemplateSetMixin(object):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(email_template_set=self.get_email_template_for_request())
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_email_template_for_request(self):
        """
        Given a request lookup the email_template associated with the user of the request.
        If the user has not email template setup raises exception.
        :param request: Request
        :return: EmailTemplateSet
        """
        try:
            email_template_set_id = self.request.data.get('email_template_set_id')
            if email_template_set_id:
                return EmailTemplateSet.get_for_user(self.request.user).get(pk=email_template_set_id)
            user_email_template_set = UserEmailTemplateSet.objects.get(user=self.request.user)
            return user_email_template_set.email_template_set
        except UserEmailTemplateSet.DoesNotExist:
            raise ValidationError(EMAIL_TEMPLATES_NOT_SETUP_MSG)

    def prevent_null_email_template_set(self):
        """
        Raises ValidationError with message if self.get_object().email_template_set is None
        """
        if not self.get_object().email_template_set:
            raise ValidationError(ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG)


class DeliveryViewSet(ModelWithEmailTemplateSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows deliveries to be viewed or edited.
    """
    serializer_class = DeliverySerializer
    queryset = DDSDelivery.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('project_id', 'from_user_id', 'to_user_id')

    # Overriding create so that we attempt to create a transfer before saving to database
    def create(self, request, *args, **kwargs):
        if request.data.get('transfer_id'):
            raise ValidationError('Deliveries may not be created with a transfer_id, '
                                  'these are generated by Duke Data Service')
        dds_util = DDSUtil(request.user)
        project_transfer = dds_util.create_project_transfer(request.data['project_id'],
                                                            request.data['to_user_id'])
        request.data['transfer_id'] = project_transfer['id']
        return super(DeliveryViewSet, self).create(request, args, kwargs)

    @action(detail=True, methods=['POST'])
    def send(self, request, pk=None):
        delivery = self.get_object()
        self.prevent_null_email_template_set()
        if not delivery.is_new() and not get_force_param(request):
            raise AlreadyNotifiedException(detail='Delivery already in progress')
        accept_url = build_accept_url(request, delivery.transfer_id, 'dds')
        message_factory = DDSMessageFactory(delivery, request.user)
        message = message_factory.make_delivery_message(accept_url)
        message.send()
        delivery.mark_notified(message.email_text)
        return self.retrieve(request)

    @action(detail=True, methods=['POST'])
    def cancel(self, request, pk=None):
        delivery = self.get_object()
        self.prevent_null_email_template_set()
        if delivery.state != State.NEW and delivery.state != State.NOTIFIED:
             raise ValidationError('Only deliveries in new and notified state can be canceled.')
        dds_util = DDSUtil(request.user)
        dds_util.cancel_project_transfer(delivery.transfer_id)
        message_factory = DDSMessageFactory(delivery, request.user)
        message = message_factory.make_canceled_message()
        message.send()
        delivery.mark_canceled()
        return self.retrieve(request)


class ShareViewSet(ModelWithEmailTemplateSetMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows shares to be viewed or edited.
    """
    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('project_id', 'from_user_id', 'to_user_id')

    @action(detail=True, methods=['POST'])
    def send(self, request, pk=None):
        share = self.get_object()
        self.prevent_null_email_template_set()
        if share.is_notified() and not get_force_param(request):
            raise AlreadyNotifiedException()
        message_factory = DDSMessageFactory(share, request.user)
        message = message_factory.make_share_message()
        message.send()
        share.mark_notified(message.email_text)
        return self.retrieve(request)


def get_force_param(request):
    """
    Return value of 'force' in request or False if not found.
    :param request: request that may contain 'force' data param
    :return: boolean
    """
    field_name = 'force'
    if field_name in request.query_params:
        force = request.query_params[field_name]
    elif 'force' in request.data:
        force = request.data[field_name]
    else:
        force = False
    return force
