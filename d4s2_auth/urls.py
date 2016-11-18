from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^authorize/$', views.authorize, name='d4s2_auth-authorize'),
    url(r'^code/$', views.authorize_callback, name='d4s2_auth-callback'),
]
