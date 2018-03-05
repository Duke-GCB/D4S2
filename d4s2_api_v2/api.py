from d4s2_api.views import DeliveryViewSet

from rest_framework import viewsets, permissions
from rest_framework.exceptions import APIException
from switchboard.dds_util import DDSUser, DDSProject, DDSProjectTransfer
from switchboard.dds_util import DDSUtil
from d4s2_api_v2.serializers import DDSUserSerializer, DDSProjectSerializer, DDSProjectTransferSerializer
from d4s2_api.models import Delivery, Share, DeliveryShareUser


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
        for delivery in Delivery.objects.filter(from_user_id=current_dds_user.id):
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
