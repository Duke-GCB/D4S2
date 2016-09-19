from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException
from rest_framework.decorators import detail_route
from handover_api.models import DukeDSUser, Handover, Share
from handover_api.serializers import UserSerializer, HandoverSerializer, ShareSerializer
from handover_api.utils import ShareMessage, HandoverMessage
from switchboard.dds_util import DDSUtil, ModelPopulator
from django.core.urlresolvers import reverse

class PopulatingAuthenticatedModelViewSet(viewsets.ModelViewSet):
    """
    Base class for requiring authentication for access
    """
    permission_classes = (permissions.IsAdminUser,)

    def __init__(self, **kwargs):
        super(PopulatingAuthenticatedModelViewSet, self).__init__(**kwargs)
        self._lazy_model_populator = None

    @property
    def model_populator(self):
        if self._lazy_model_populator is None:
            request_dds_user = DukeDSUser.objects.get(user=self.request.user)
            dds_util = DDSUtil(user_id=request_dds_user.dds_id)
            self._lazy_model_populator = ModelPopulator(dds_util)
        return self._lazy_model_populator

    def save_and_populate(self, serializer):
        # Must be overridden by subclass
        pass

    def perform_create(self, serializer):
        self.save_and_populate(serializer)

    def perform_update(self, serializer):
        self.save_and_populate(serializer)

    def populate_user(self, dds_user):
        self.model_populator.populate_user(dds_user)

    def populate_project(self, dds_project):
        self.model_populator.populate_project(dds_project)


class UserViewSet(PopulatingAuthenticatedModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = DukeDSUser.objects.all()
    serializer_class = UserSerializer
    filter_fields = ('dds_id',)

    def save_and_populate(self, serializer):
        dds_user = serializer.save()
        self.populate_user(dds_user)


class TransferViewSet(PopulatingAuthenticatedModelViewSet):
    """
    Base view set for handovers and shares, both of which can be filtered by
    project_id, from_user_id, to_user_id

    """
    model = None
    def get_queryset(self):
        """
        Optionally filters on project_id, from_user_id, or to_user_id
        Originally we could just specify filter_fields as project_id, from_user_id, and to_user_id
        but these don't work across relationships (requires project__project_id) despite serializer field project_id
        So this method implements the filtering manually
        """
        queryset = self.model.objects.all()
        project_id = self.request.query_params.get('project_id', None)
        if project_id is not None:
            queryset = queryset.filter(project__project_id=project_id)
        from_user_id = self.request.query_params.get('from_user_id', None)
        if from_user_id is not None:
            queryset = queryset.filter(from_user__dds_id=from_user_id)
        to_user_id = self.request.query_params.get('to_user_id', None)
        if to_user_id is not None:
            queryset = queryset.filter(to_user__dds_id=to_user_id)
        return queryset

    def save_and_populate(self, serializer):
        transfer = serializer.save()
        self.populate_project(transfer.project)
        for dds_user in [transfer.from_user, transfer.to_user]:
            self.populate_user(dds_user)


class HandoverViewSet(TransferViewSet):
    """
    API endpoint that allows handovers to be viewed or edited.
    """
    serializer_class = HandoverSerializer
    model = Handover

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


class ShareViewSet(TransferViewSet):
    """
    API endpoint that allows shares to be viewed or edited.
    """
    serializer_class = ShareSerializer
    model = Share

    @detail_route(methods=['POST'])
    def send(self, request, pk=None):
        share = self.get_object()
        if 'force' in request.data:
            force = request.data['force']
        else:
            force = False
        if share.is_notified() and not force:
            raise AlreadyNotifiedException()
        message = ShareMessage(share)
        message.send()
        share.mark_notified(message.email_text)
        return self.retrieve(request)
