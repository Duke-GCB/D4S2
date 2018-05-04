from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api_v1 import api

router = routers.DefaultRouter()
router.register(r'deliveries', api.DeliveryViewSet, 'ddsdelivery')
router.register(r'shares', api.ShareViewSet, 'share')

urlpatterns = [
    url(r'^', include(router.urls)),
]
