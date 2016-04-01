from django.conf.urls import url, include
from rest_framework import routers
from handover_api import views

router = routers.DefaultRouter()
router.register(r'handovers', views.HandoverViewSet)
router.register(r'drafts', views.DraftViewSet)
router.register(r'users', views.UserViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
]
