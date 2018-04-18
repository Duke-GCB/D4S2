from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.decorators import list_route, detail_route
from rest_framework.response import Response
from django.db.models import Q
from django.core.urlresolvers import reverse
from switchboard.dds_util import DDSUser, DDSProject, DDSProjectTransfer
from switchboard.dds_util import DDSUtil
from switchboard.s3_util import S3DeliveryUtil
from d4s2_api_v2.serializers import DDSUserSerializer, DDSProjectSerializer, DDSProjectTransferSerializer, \
    UserSerializer, S3EndpointSerializer, S3UserSerializer, S3BucketSerializer, S3DeliverySerializer
from d4s2_api.models import DDSDelivery, S3Endpoint, S3User, S3UserTypes, S3Bucket, S3Delivery
from d4s2_api.views import AlreadyNotifiedException, get_force_param, DeliveryViewSet
from switchboard.s3_util import S3DeliveryMessage


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


class BadRequestException(APIException):
    status_code = 400
    def __init__(self, detail):
        self.detail = detail


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
        full_name_contains = self.request.query_params.get('full_name_contains', None)
        recent = self.request.query_params.get('recent', None)

        dds_util = DDSUtil(self.request.user)
        if recent:
            if full_name_contains:
                msg = "Query parameter 'full_name_contains' not allowed when specifying the 'recent' query parameter."
                raise BadRequestException(msg)
            return self._get_recent_delivery_users(dds_util)
        else:
            return self._ds_operation(DDSUser.fetch_list, dds_util, full_name_contains)

    def _get_recent_delivery_users(self, dds_util):
        """
        Return users that are the recipient of deliveries create by the current user.
        :param dds_util: DDSUtil: connection to DukeDS
        :return: [DDSUser]: users who received deliveries from the current user
        """
        current_dds_user = dds_util.get_current_user()
        to_user_ids = set()
        for delivery in DDSDelivery.objects.filter(from_user_id=current_dds_user.id):
            to_user_ids.add(delivery.to_user_id)
            for share_user in delivery.share_users.all():
                if share_user.dds_id != current_dds_user.id:
                    to_user_ids.add(share_user.dds_id)
        return self._ds_operation(self._fetch_users_for_ids, dds_util, to_user_ids)

    def _fetch_users_for_ids(self, dds_util, to_user_ids):
        """
        Given a list of DukeDS user ids fetch user details.
        :param dds_util: DDSUtil: connection to DukeDS
        :param to_user_ids: [str]: list of DukeDS user UUIDs
        :return: [DDSUser]: list of user details fetched from DukeDS
        """
        users = []
        for to_user_id in to_user_ids:
            users.append(DDSUser.fetch_one(dds_util, to_user_id))
        return users

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
        dds_project_id = self.kwargs.get('pk')
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProject.fetch_one, dds_util, dds_project_id)


class DDSProjectTransfersViewSet(DDSViewSet):

    serializer_class = DDSProjectTransferSerializer

    def get_queryset(self):
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProjectTransfer.fetch_list, dds_util)

    def get_object(self):
        dds_project_transfer_id = self.kwargs.get('pk')
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProjectTransfer.fetch_one, dds_util, dds_project_transfer_id)


class UserViewSet(viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    @list_route(methods=['get'], url_path='current-user')
    def current_user(self, request):
        current_user = self.request.user
        serializer = UserSerializer(self.request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class S3EndpointViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = S3EndpointSerializer
    queryset = S3Endpoint.objects.all()


class S3UserViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = S3UserSerializer

    def get_queryset(self):
        """
        Allows filtering by email query param only showing normal users
        """
        email = self.request.query_params.get('email')
        queryset = S3User.objects.filter(type=S3UserTypes.NORMAL)
        if email:
            return queryset.filter(user__email=email)
        return queryset


class S3BucketViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = S3BucketSerializer

    def get_queryset(self):
        """
        Users can only see buckets they own or a user received a a delivery
        """
        return S3Bucket.objects.filter(
            Q(owner__user=self.request.user) |
            Q(deliveries__to_user__user=self.request.user)
        )


class S3DeliveryViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = S3DeliverySerializer

    def get_queryset(self):
        """
        Users can only see the deliveries they sent or received.
        """
        return S3Delivery.objects.filter(Q(from_user__user=self.request.user) | Q(to_user__user=self.request.user))

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        s3_delivery = self.get_object()
        if not s3_delivery.is_new() and not get_force_param(request):
            raise AlreadyNotifiedException(detail='S3 Delivery already in progress')
        # TODO create app to handle s3ownership UI
        # accept_path = reverse('s3ownership-prompt') + "?s3_delivery_id=" + str(s3_delivery.id)
        # accept_url = request.build_absolute_uri(accept_path)
        accept_url = 'TODO'
        s3_delivery_util = S3DeliveryUtil(s3_delivery, request.user)
        s3_delivery_util.give_agent_permissions()
        message = S3DeliveryMessage(s3_delivery, request.user, accept_url)
        message.send()
        s3_delivery.mark_notified(message.email_text)
        return self.retrieve(request)
