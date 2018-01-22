from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import detail_route

from django.core.urlresolvers import reverse

from d4s2_api_v2.serializers import *
from d4s2_api_v2.models import *


class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DeliverySerializer

    def get_queryset(self):
        duke_ds_user = DukeDSUser.objects.filter(user=self.request.user).first()
        return Delivery.objects.filter(from_user_id=duke_ds_user.dds_id)


# class DukeDSUserViewSet(viewsets.ReadOnlyModelViewSet):
#
#     permission_classes = (permissions.IsAuthenticated,)
#     serializer_class = DukeDSUserSerializer
#     queryset = DukeDSUser.objects.all()
#
#
# class DukeDSProjectViewSet(viewsets.ReadOnlyModelViewSet):
#
#     permission_classes = (permissions.IsAuthenticated,)
#     serializer_class = DukeDSProjectSerializer
#
#     def get_queryset(self):
#         # Only show the projects that the authenticated user is delivering
#         dds_user = DukeDSUser.objects.filter(user=self.request.user).first()
#         return DukeDSProject.objects.filter(delivery__from_user_id=dds_user.dds_id)


