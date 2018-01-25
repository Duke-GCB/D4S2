from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api import views

router = routers.DefaultRouter()
router.register(r'deliveries', views.DeliveryViewSet, 'delivery')
router.register(r'shares', views.ShareViewSet, 'share')

urlpatterns = [
    url(r'^', include(router.urls)),
]
