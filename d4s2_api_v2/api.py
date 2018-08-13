from rest_framework import viewsets, permissions, status, views
from rest_framework.exceptions import APIException
from rest_framework.decorators import list_route, detail_route
from rest_framework.response import Response
from django.db.models import Q
from django.core.urlresolvers import reverse
from django_filters.rest_framework import DjangoFilterBackend
from switchboard.dds_util import DDSUser, DDSProject, DDSProjectTransfer, DDSProjectPermissions
from switchboard.dds_util import DDSUtil, MessageFactory
from switchboard.s3_util import S3BucketUtil
from d4s2_api_v2.serializers import DDSUserSerializer, DDSProjectSerializer, DDSProjectTransferSerializer, \
    UserSerializer, S3EndpointSerializer, S3UserSerializer, S3BucketSerializer, S3DeliverySerializer, \
    DDSProjectPermissionSerializer
from d4s2_api.models import DDSDelivery, S3Endpoint, S3User, S3UserTypes, S3Bucket, S3Delivery
from d4s2_api_v1.api import AlreadyNotifiedException, get_force_param, DeliveryViewSet, build_accept_url
from switchboard.s3_util import S3MessageFactory, S3Exception, S3NoSuchBucket, SendDeliveryOperation
from d4s2_api_v1.serializers import DeliverySerializer


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


class WrappedS3Exception(APIException):
    """
    Converts error returned from DukeDS python code into one appropriate for django.
    """
    def __init__(self, s3_exception, status_code=500):
        self.detail = str(s3_exception)
        self.status_code = status_code


class InvalidSettingsException(APIException):
    """
    Raised when the database settings tables are not setup correctly.
    """
    status_code = 500
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

    @list_route(methods=['get'], url_path='current-duke-ds-user')
    def current_duke_ds_user(self, request):
        dds_util = DDSUtil(self.request.user)
        remote_dds_user = dds_util.get_current_user()
        serializer = DDSUserSerializer(remote_dds_user)
        return Response(serializer.data, status=status.HTTP_200_OK)


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

    @detail_route(methods=['get'], serializer_class=DDSProjectPermissionSerializer)
    def permissions(self, request, pk=None):
        dds_util = DDSUtil(request.user)
        user_id = request.query_params.get('user')
        project_permissions = self._ds_operation(DDSProjectPermissions.fetch_list, dds_util, pk, user_id)
        serializer = DDSProjectPermissionSerializer(project_permissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name', )


class S3UserViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = S3UserSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('endpoint',  'user')

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
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name', )

    def get_queryset(self):
        """
        Users can only see buckets they own or a user received a a delivery
        """
        return S3Bucket.objects.filter(
            Q(owner__user=self.request.user) |
            Q(deliveries__to_user__user=self.request.user)
        )

    def create(self, request, *args, **kwargs):
        self.verify_user_owns_bucket_in_s3(request)
        return super(S3BucketViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.verify_user_owns_bucket_in_s3(request)
        return super(S3BucketViewSet, self).update(request, *args, **kwargs)

    @staticmethod
    def verify_user_owns_bucket_in_s3(request):
        """
        Make sure user can list the bucket specified.
        Raises BadRequestException if bucket is not found
        :param request: request who's data we will validate
        """
        user = request.user
        endpoint_id = request.data['endpoint']
        bucket_name = request.data['name']
        endpoint = S3Endpoint.objects.get(pk=endpoint_id)
        s3_bucket_util = S3BucketUtil(endpoint, user)
        try:
            if not s3_bucket_util.user_owns_bucket(bucket_name):
                raise BadRequestException("Your user do not own bucket {}.".format(bucket_name))
        except S3NoSuchBucket as e:
            raise BadRequestException(str(e))
        except S3Exception as e:
            raise WrappedS3Exception(e)


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
        accept_url = build_accept_url(request, s3_delivery.transfer_id, 's3')
        SendDeliveryOperation.run(s3_delivery, accept_url)
        return self.retrieve(request)


class PreviewDDSDelivery(object):
    def __init__(self, from_user_id, to_user_id, project_id, user_message):
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.project_id = project_id
        self.user_message = user_message
        self.delivery_email_text = ''



from rest_framework import serializers
from switchboard.dds_util import DeliveryDetails

class PreviewDDSDeliverySerializer(serializers.Serializer):

    from_user_id = serializers.CharField(required=True)
    to_user_id = serializers.CharField(required=True)
    project_id = serializers.CharField(required=True)
    user_message = serializers.CharField(allow_blank=True)
    delivery_email_text = serializers.CharField(read_only=True)


class DeliveryPreviewView(views.APIView):

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        # Deserialize a delivery from the incoming payload
        serializer = PreviewDDSDeliverySerializer(data=request.data)
        serializer.is_valid(True)
        delivery_preview = PreviewDDSDelivery(**serializer.validated_data)

        accept_url = 'accept-url-goes-here'
        delivery_details = DeliveryDetails(delivery_preview, request.user)

        message_factory = MessageFactory(delivery_details)
        message = message_factory.make_delivery_message(accept_url)
        delivery_preview.delivery_email_text = message.email_text
        serializer = DeliverySerializer(delivery_preview)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
