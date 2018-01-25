from d4s2_api.views import DeliveryViewSet

from rest_framework import viewsets, permissions
from rest_framework.exceptions import APIException
from switchboard.dds_util import DDSUser, DDSProject
from switchboard.dds_util import DDSUtil
from d4s2_api_v2.serializers import DDSUserSerializer, DDSProjectSerializer


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
