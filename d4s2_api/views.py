from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import detail_route
from d4s2_api.models import Delivery, Share
from d4s2_api.serializers import DeliverySerializer, ShareSerializer, DDSUserSerializer, DDSProjectSerializer
from switchboard.dds_util import DDSUser, DDSProject
from d4s2_api.utils import ShareMessage, DeliveryMessage
from switchboard.dds_util import DDSUtil
from django.core.urlresolvers import reverse
from django_filters.rest_framework import DjangoFilterBackend


class DataServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Data Service temporarily unavailable, try again later.'


class WrappedDataServiceException(APIException):
    """
    Converts error returned from DukeDS python code into one appropriate for django.
    """
    def __init__(self, data_service_exception):
        self.status_code = data_service_exception.status_code
        self.detail = data_service_exception.message


class AlreadyNotifiedException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Already notified'


class DeliveryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows deliveries to be viewed or edited.
    """
    serializer_class = DeliverySerializer
    queryset = Delivery.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('project_id', 'from_user_id', 'to_user_id')

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        delivery = self.get_object()
        if not delivery.is_new():
            raise AlreadyNotifiedException(detail='Delivery already in progress')
        accept_path = reverse('ownership-prompt') + "?transfer_id=" + str(delivery.transfer_id)
        accept_url = request.build_absolute_uri(accept_path)
        message = DeliveryMessage(delivery, request.user, accept_url)
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
        if 'force' in request.data:
            force = request.data['force']
        else:
            force = False
        if share.is_notified() and not force:
            raise AlreadyNotifiedException()
        message = ShareMessage(share, request.user)
        message.send()
        share.mark_notified(message.email_text)
        return self.retrieve(request)


class DDSViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)

    def _ds_operation(self, func, *args):
        try:
            return func(*args)
        except WrappedDataServiceException:
            raise # passes along status code, e.g. 404
        except Exception as e:
            raise DataServiceUnavailable(e)


class DDSUsersViewSet(DDSViewSet):
    """
    Interfaces with DukeDS API to provide project listing and details.
    Though it is not backed by django models, the ReadOnlyModelViewSet base class
    still works well
    """
    serializer_class = DDSUserSerializer

    def get_queryset(self):
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSUser.fetch_list, dds_util)

    def get_object(self):
        dds_user_id = self.kwargs.get('pk')
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSUser.fetch_one, dds_util, dds_user_id)


class DDSProjectsViewSet(DDSViewSet):
    """
    Interfaces with DukeDS API to provide project listing and details.
    Though it is not backed by django models, the ReadOnlyModelViewSet base class
    still works well
    """
    serializer_class = DDSProjectSerializer

    def get_queryset(self):
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProject.fetch_list, dds_util)

    def get_object(self):
        dds_user_id = self.kwargs.get('pk')
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProject.fetch_one, dds_util, dds_user_id)
