from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import detail_route

from django.core.urlresolvers import reverse

from d4s2_api_v2.serializers import *
from models import *

class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DeliverySerializer

    def get_queryset(self):
        return Delivery.objects.filter(from_user__user=self.request.user)

class DukeDSUserViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DukeDSUserSerializer
    queryset = DukeDSUser.objects.all()

class DukeDSProjectViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DukeDSProjectSerializer

    def get_queryset(self):
        # Only show the projects that the authenticated user is delivering
        return DukeDSProject.objects.filter(delivery__from_user__user=self.request.user)


