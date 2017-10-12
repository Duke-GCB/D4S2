from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api_v2 import api

router = routers.DefaultRouter()
router.register(r'deliveries', api.DeliveryViewSet, 'delivery')
router.register(r'duke-ds-users', api.DukeDSUserViewSet, 'dukedsuser')
router.register(r'duke-ds-projects', api.DukeDSProjectViewSet, 'dukedsproject')

urlpatterns = [
    url(r'^', include(router.urls)),
]
