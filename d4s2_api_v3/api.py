from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.decorators import action
from rest_framework.response import Response
from switchboard.userservice import get_users_for_query, get_user_for_netid, get_netid_from_user
from switchboard.storage import get_projects_for_user, get_project_for_user
from d4s2_api_v3.serializers import UserSerializer, ProjectSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    def get_queryset(self):
        query = self.request.query_params.get('query', None)
        if not query:
            raise APIException(detail="Error: The query parameter is required.", code=400)
        if len(query) < 3:
            raise APIException(detail="The query parameter must be at least 3 characters.", code=400)
        return get_users_for_query(query)

    def get_object(self):
        pk = self.kwargs.get('pk')
        return get_user_for_netid(netid=pk)

    @action(detail=False, methods=['get'], url_path='current-user')
    def current_user(self, request):
        # strip off trailing @ and domain from username
        netid = get_netid_from_user(self.request.user)
        person = get_user_for_netid(netid)
        serializer = UserSerializer(person)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Interfaces with DukeDS API to provide project listing and details.
    Though it is not backed by django models, the ReadOnlyModelViewSet base class
    still works well
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return get_projects_for_user(self.request.user)

    def get_object(self):
        return get_project_for_user(self.kwargs.get('pk'))
        dds_util = DDSUtil(self.request.user)
        return self._ds_operation(DDSProject.fetch_one, dds_util, dds_project_id)

    # TODO permissions
    # TODO summary
