from rest_framework import viewsets, permissions, status, generics
from rest_framework.exceptions import APIException
from rest_framework.decorators import list_route, detail_route
from rest_framework.response import Response
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from switchboard.dds_util import DDSUser, DDSProject, DDSProjectTransfer, DDSProjectPermissions, DDSProjectSummary
from switchboard.dds_util import DDSUtil, DDSMessageFactory, DDSAuthProvider, DDSAffiliate, DataServiceError
from switchboard.s3_util import S3BucketUtil
from d4s2_api_v2.serializers import DDSUserSerializer, DDSProjectSerializer, DDSProjectTransferSerializer, \
    UserSerializer, S3EndpointSerializer, S3UserSerializer, S3BucketSerializer, S3DeliverySerializer, \
    DDSProjectPermissionSerializer, DDSDeliveryPreviewSerializer, DDSAuthProviderSerializer, DDSAffiliateSerializer, \
    AddUserSerializer, DDSProjectSummarySerializer, EmailTemplateSetSerializer, EmailTemplateSerializer
from d4s2_api.models import DDSDelivery, S3Endpoint, S3User, S3UserTypes, S3Bucket, S3Delivery, EmailTemplateSet, \
    EmailTemplate
from d4s2_api_v1.api import AlreadyNotifiedException, get_force_param, build_accept_url, DeliveryViewSet, \
    ModelWithEmailTemplateSetMixin
from switchboard.s3_util import S3Exception, S3NoSuchBucket, SendDeliveryOperation
from d4s2_api_v2.models import DDSDeliveryPreview
from gcb_web_auth.models import GroupManagerConnection
from gcb_web_auth.groupmanager import get_users_group_names
from gcb_web_auth.utils import get_default_oauth_service, current_user_details, OAuthConfigurationException


class DataServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Data Service temporarily unavailable, try again later.'


class WrappedDataServiceException(APIException):
    """
    Converts error returned from DukeDS python code into one appropriate for django.
    """
    def __init__(self, data_service_error):
        self.status_code = data_service_error.status_code
        self.detail = str(data_service_error)


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
        except DataServiceError as e:
            raise WrappedDataServiceException(e)
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
        email = self.request.query_params.get('email', None)
        username = self.request.query_params.get('username', None)
        recent = self.request.query_params.get('recent', None)

        dds_util = DDSUtil(self.request.user)
        if recent:
            if full_name_contains:
                msg = "Query parameter 'full_name_contains' not allowed when specifying the 'recent' query parameter."
                raise BadRequestException(msg)
            return self._get_recent_delivery_users(dds_util)
        else:
            return self._ds_operation(DDSUser.fetch_list, dds_util, full_name_contains, email, username)

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

    @detail_route(methods=['get'], url_path='summary', serializer_class=DDSProjectSummarySerializer)
    def summary(self, request, pk=None):
        dds_util = DDSUtil(request.user)
        project_summary = self._ds_operation(DDSProjectSummary.fetch_one, dds_util, pk)
        serializer = DDSProjectSummarySerializer(project_summary)
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


class S3DeliveryViewSet(ModelWithEmailTemplateSetMixin, viewsets.ModelViewSet):
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
        self.prevent_null_email_template_set()
        if not s3_delivery.is_new() and not get_force_param(request):
            raise AlreadyNotifiedException(detail='S3 Delivery already in progress')
        accept_url = build_accept_url(request, s3_delivery.transfer_id, 's3')
        SendDeliveryOperation.run(s3_delivery, accept_url)
        return self.retrieve(request)


class DeliveryPreviewView(ModelWithEmailTemplateSetMixin, generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DDSDeliveryPreviewSerializer

    def create(self, request, *args, **kwargs):
        email_template_set = self.get_email_template_for_request()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        delivery_preview = DDSDeliveryPreview(**serializer.validated_data)
        delivery_preview.email_template_set = email_template_set

        accept_url = build_accept_url(request, delivery_preview.transfer_id, 'dds')
        message_factory = DDSMessageFactory(delivery_preview, self.request.user)
        message = message_factory.make_delivery_message(accept_url)
        delivery_preview.delivery_email_text = message.email_text
        serializer = self.get_serializer(instance=delivery_preview)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DDSAuthProviderViewSet(DDSViewSet):
    """
    This ViewSet proxies search and listing of Auth Providers though Duke DS
    The pk/id for these endpoints shall be the UUID of the auth provider as registered in DukeDS

    """
    serializer_class = DDSAuthProviderSerializer

    def get_queryset(self):
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSAuthProvider.fetch_list, dds_util)

    def get_object(self):
        provider_id = self.kwargs.get('pk')
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSAuthProvider.fetch_one, dds_util, provider_id)


class DDSAuthProviderAffiliatesViewSet(DDSViewSet):
    """
    This ViewSet proxies search and listing of Auth Provider Affiliates (user accounts) through Duke DS
    Fetching affiliates requires an auth provider ID, which we will typically use the openid auth provider
    known to gcb_web_auth
    """

    serializer_class = DDSAffiliateSerializer

    def _get_auth_provider_id(self):
        default_auth_provider_id = DDSUtil.get_openid_auth_provider_id()
        auth_provider_id = self.request.query_params.get('auth_provider_id', default_auth_provider_id)
        return auth_provider_id

    def get_queryset(self):
        dds_util = DDSUtil(self.request.user)
        auth_provider_id = self._get_auth_provider_id()
        full_name_contains = self.request.query_params.get('full_name_contains')
        email = self.request.query_params.get('email', None)
        username = self.request.query_params.get('username', None)
        return self._ds_operation(DDSAffiliate.fetch_list, dds_util, auth_provider_id, full_name_contains, email, username)

    def get_object(self):
        dds_util = DDSUtil(self.request.user)
        auth_provider_id = self._get_auth_provider_id()
        uid = self.kwargs.get('pk')
        return self._ds_operation(DDSAffiliate.fetch_one, dds_util, auth_provider_id, uid)

    @detail_route(methods=['POST'], serializer_class=DDSUserSerializer, url_path='get-or-register-user')
    def get_or_register_user(self, request, pk):
        dds_util = DDSUtil(self.request.user)
        auth_provider_id = self._get_auth_provider_id()
        dds_user = self._ds_operation(DDSUser.get_or_register_user, dds_util, auth_provider_id, pk)
        serializer = DDSUserSerializer(dds_user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EmailTemplateSetViewSet(viewsets.ReadOnlyModelViewSet):
    @staticmethod
    def get_users_group_names(user):
        try:
            user_details = current_user_details(get_default_oauth_service(), user)
            duke_unique_id = user_details['dukeUniqueID']
            group_manager_connection = GroupManagerConnection.objects.first()
            if group_manager_connection and duke_unique_id:
                group_manager_groups = get_users_group_names(group_manager_connection, duke_unique_id)
                return [group_name for group_name in group_manager_groups if group_name]
            else:
                return []
        except OAuthConfigurationException:
            return []

    def get_queryset(self):
        """
        Include a users default template set and those for the current user's groups.
        """
        current_user_groups = self.get_users_group_names(self.request.user)
        return EmailTemplateSet.objects.filter(
            Q(useremailtemplateset__user=self.request.user) |
            Q(group_name__in=current_user_groups)
        )

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = EmailTemplateSetSerializer
    queryset = EmailTemplateSet.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('name', )


class EmailTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        """
        Include a users default template set and those for the current user's groups.
        """
        current_user_groups = EmailTemplateSetViewSet.get_users_group_names(self.request.user)
        return EmailTemplate.objects.filter(
            Q(template_set__useremailtemplateset__user=self.request.user) |
            Q(template_set__group_name__in=current_user_groups)
        )

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = EmailTemplateSerializer
    queryset = EmailTemplate.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filter_fields = ('template_set', )
