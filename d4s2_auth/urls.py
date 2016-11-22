from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^authorize/$', views.authorize, name='authorize'),
    url(r'^code_callback/$', views.authorize_callback, name='callback'),
    url(r'^home/$', views.user_details, name='home'),
    url(r'^login/$', views.login_page, name='login'),
]
