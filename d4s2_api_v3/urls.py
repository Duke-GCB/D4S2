from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api_v3 import api

router = routers.DefaultRouter()
router.register(r'users', api.UserViewSet, 'v3-users')

urlpatterns = [
    url(r'^', include(router.urls)),
]
