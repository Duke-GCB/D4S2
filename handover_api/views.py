from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException
from rest_framework.decorators import detail_route
from handover_api.models import DukeDSUser, Handover, Draft
from handover_api.serializers import UserSerializer, HandoverSerializer, DraftSerializer
from handover_api.utils import DraftMessage, HandoverMessage
from switchboard.dds_util import DDSUtil
from django.core.urlresolvers import reverse

class AuthenticatedModelViewSet(viewsets.ModelViewSet):
    """
    Base class for requiring authentication for access
    """
    permission_classes = (permissions.IsAdminUser,)

class UserViewSet(AuthenticatedModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = DukeDSUser.objects.all()
    serializer_class = UserSerializer
    filter_fields = ('dds_id',)

    def perform_create(self, serializer):
        """
        Overrides perform_create to fetch user details from DukeDS if not provided
        :param serializer: A serialized representation of the user to create
        """
        # First, save the serializer to create an instance
        dds_user = serializer.save()
        if dds_user.full_name is None or dds_user.email is None:
            request_dds_user = DukeDSUser.objects.get(user=self.request.user)
            dds_util = DDSUtil(user_id=request_dds_user.dds_id)
            remote_user = dds_util.get_remote_user(dds_user.dds_id)
            dds_user.email = dds_user.email or remote_user.email
            dds_user.full_name = dds_user.full_name or remote_user.full_name
            dds_user.save()


class HandoverViewSet(AuthenticatedModelViewSet):
    """
    API endpoint that allows handovers to be viewed or edited.
    """
    queryset = Handover.objects.all()
    serializer_class = HandoverSerializer
    filter_fields = ('project_id', 'from_user_id', 'to_user_id',)

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        handover = self.get_object()
        if not handover.is_new():
            raise AlreadyNotifiedException(detail='Handover already in progress')
        accept_path = reverse('ownership-prompt') + "?token=" + str(handover.token)
        accept_url = request.build_absolute_uri(accept_path)
        message = HandoverMessage(handover, accept_url)
        message.send()
        handover.mark_notified(message.email_text)
        return self.retrieve(request)

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

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        draft = self.get_object()
        if 'force' in request.data:
            force = request.data['force']
        else:
            force = False
        if draft.is_notified() and not force:
            raise AlreadyNotifiedException()
        message = DraftMessage(draft)
        message.send()
        draft.mark_notified(message.email_text)
        return self.retrieve(request)
