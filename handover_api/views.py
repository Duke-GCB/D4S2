from rest_framework import viewsets, status, filters
from rest_framework.exceptions import APIException
from rest_framework.decorators import detail_route
from handover_api.models import User, Handover, Draft
from handover_api.serializers import UserSerializer, HandoverSerializer, DraftSerializer
from handover_api.utils import send_draft

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_fields = ('dds_id')


class HandoverViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows handovers to be viewed or edited.
    """
    queryset = Handover.objects.all()
    serializer_class = HandoverSerializer
    filter_fields = ('project_id','from_user_id','to_user_id')


class AlreadyNotifiedException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Already notified'


class DraftViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows drafts to be viewed or edited.
    """
    queryset = Draft.objects.all()
    serializer_class = DraftSerializer
    filter_fields = ('project_id','from_user_id','to_user_id')

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        draft = self.get_object()
        if draft.is_notified():
            raise AlreadyNotifiedException()
        send_draft(draft)
        draft.mark_notified(True)
        return self.retrieve(request)
