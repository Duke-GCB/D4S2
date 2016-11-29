from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^authorize/$', views.authorize, name='auth-authorize'),
    url(r'^code_callback/$', views.authorize_callback, name='auth-callback'),
    url(r'^home/$', views.home, name='auth-home'),
    url(r'^login/$', views.login_page, name='auth-login'),
    url(r'^unconfigured/$', views.unconfigured, name='auth-unconfigured'),
]
