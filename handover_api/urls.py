from django.conf.urls import url, include
from rest_framework import routers
from handover_api import views

router = routers.DefaultRouter()
router.register(r'deliveries', views.DeliveryViewSet, 'delivery')
router.register(r'shares', views.ShareViewSet, 'share')
# Previous name was drafts, so we include this for compatibility
router.register(r'drafts', views.ShareViewSet, 'draft')
router.register(r'users', views.UserViewSet, 'dukedsuser')

urlpatterns = [
    url(r'^', include(router.urls)),
]
