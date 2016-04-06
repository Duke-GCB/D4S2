from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException
from rest_framework.decorators import detail_route
from handover_api.models import DukeDSUser, Handover, Draft
from handover_api.serializers import UserSerializer, HandoverSerializer, DraftSerializer
from handover_api.utils import send_draft

class AuthenticatedModelViewSet(viewsets.ModelViewSet):
    """
    Base class for requiring authentication for access
    """
    permission_classes = (permissions.IsAuthenticated,)

class UserViewSet(AuthenticatedModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = DukeDSUser.objects.all()
    serializer_class = UserSerializer
    filter_fields = ('dds_id',)


class HandoverViewSet(AuthenticatedModelViewSet):
    """
    API endpoint that allows handovers to be viewed or edited.
    """
    queryset = Handover.objects.all()
    serializer_class = HandoverSerializer
    filter_fields = ('project_id', 'from_user_id', 'to_user_id',)


class AlreadyNotifiedException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Already notified'


class DraftViewSet(AuthenticatedModelViewSet):
    """
    API endpoint that allows drafts to be viewed or edited.
    """
    queryset = Draft.objects.all()
    serializer_class = DraftSerializer
    filter_fields = ('project_id', 'from_user_id', 'to_user_id',)
    permission_classes = (permissions.IsAuthenticated,)

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        draft = self.get_object()
        if 'force' in request.data:
            force = request.data['force']
        else:
            force = False
        if draft.is_notified() and not force:
            raise AlreadyNotifiedException()
        send_draft(draft)
        draft.mark_notified(True)
        return self.retrieve(request)
