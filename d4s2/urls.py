from django.conf.urls import url, include

from django.contrib import admin
from django.views.generic.base import RedirectView
from django.contrib.auth import views as auth_views
from rest_framework.authtoken import views as authtoken_views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ownership/', include('ownership.urls')),
    url(r'^auth/', include('d4s2_auth.urls')),
    url(r'^api/v1/', include('d4s2_api.urls')),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^api-token-auth/', authtoken_views.obtain_auth_token),
    # ownership-themed login/logout pages
    url(r'^accounts/login/$', auth_views.login, {'template_name': 'd4s2_auth/login.html' }, name='login'),
    url(r'^accounts/logout/$', auth_views.logout, {'template_name': 'd4s2_auth/logged_out.html' }, name='logout'),
    # Redirect / to /accounts/login
    url(r'^$', RedirectView.as_view(pattern_name='auth-home', permanent=False)),
]
