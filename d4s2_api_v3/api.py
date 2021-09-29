from rest_framework import viewsets, permissions, status, generics
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.urls import reverse
from switchboard.userservice import get_users_for_query, get_user_for_netid, get_netid_from_user
from d4s2_api_v3.serializers import UserSerializer


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
