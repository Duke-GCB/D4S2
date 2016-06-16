from django.conf.urls import url, include
from rest_framework import routers
from handover_api import views

router = routers.DefaultRouter()
router.register(r'handovers', views.HandoverViewSet, 'handover')
router.register(r'drafts', views.DraftViewSet, 'draft')
router.register(r'users', views.UserViewSet, 'dukedsuser')

urlpatterns = [
    url(r'^', include(router.urls)),
]
