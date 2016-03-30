from django.conf.urls import url, include
from django.contrib import admin
from handover_api import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'handovers', views.HandoverViewSet)
router.register(r'drafts', views.DraftViewSet)
router.register(r'users', views.UserViewSet)


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^', include(router.urls)),
]
