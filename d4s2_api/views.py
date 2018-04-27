from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import detail_route
from d4s2_api.models import DDSDelivery, Share
from d4s2_api.serializers import DeliverySerializer, ShareSerializer
from switchboard.dds_util import DDSUtil, DDSShareMessage, DDSDeliveryMessage
from django.core.urlresolvers import reverse
from django_filters.rest_framework import DjangoFilterBackend


class AlreadyNotifiedException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Already notified'


class DeliveryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows deliveries to be viewed or edited.
    """
    serializer_class = DeliverySerializer
    queryset = DDSDelivery.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('project_id', 'from_user_id', 'to_user_id')

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        delivery = self.get_object()
        if not delivery.is_new() and not get_force_param(request):
            raise AlreadyNotifiedException(detail='Delivery already in progress')
        accept_path = reverse('ownership-prompt') + "?transfer_id=" + str(delivery.transfer_id)
        accept_url = request.build_absolute_uri(accept_path)
        message = DDSDeliveryMessage(delivery, request.user, accept_url)
        message.send()
        delivery.mark_notified(message.email_text)
        return self.retrieve(request)

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


class ShareViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows shares to be viewed or edited.
    """
    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('project_id', 'from_user_id', 'to_user_id')

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        share = self.get_object()
        if share.is_notified() and not get_force_param(request):
            raise AlreadyNotifiedException()
        message = DDSShareMessage(share, request.user)
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
