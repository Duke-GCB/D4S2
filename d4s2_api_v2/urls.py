from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api_v2 import api

router = routers.DefaultRouter()
router.register(r'deliveries', api.DeliveryViewSet, 'v2-delivery')
router.register(r'duke-ds-users', api.DDSUsersViewSet, 'v2-dukedsuser')
router.register(r'duke-ds-projects', api.DDSProjectsViewSet, 'v2-dukedsproject')
router.register(r'duke-ds-project-transfers', api.DDSProjectTransfersViewSet, 'v2-dukedsprojecttransfer')
router.register(r'users', api.UserViewSet, 'v2-users')

urlpatterns = [
    url(r'^', include(router.urls)),
]
