from django.conf.urls import url
from django.views.generic.base import TemplateView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    url(r'^authorize/$', views.authorize, name='auth-authorize'),
    url(r'^code_callback/$', views.authorize_callback, name='auth-callback'),
    url(r'^home/$', views.home, name='auth-home'),
    url(r'^unconfigured/$', TemplateView.as_view(template_name='gcb_web_auth/unconfigured.html'), name='auth-unconfigured'),
]
