from rest_framework import viewsets
from handover_api.models import User, Handover, Draft
from handover_api.serializers import UserSerializer, HandoverSerializer, DraftSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer


class HandoverViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows handovers to be viewed or edited.
    """
    queryset = Handover.objects.all()
    serializer_class = HandoverSerializer


class DraftViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows drafts to be viewed or edited.
    """
    queryset = Draft.objects.all()
    serializer_class = DraftSerializer