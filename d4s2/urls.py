from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.contrib.auth import views as auth_views
from rest_framework.authtoken import views as authtoken_views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ownership/', include('ownership.urls')),
    url(r'^download/', include('download_service.urls')),
    url(r'^auth/', include('gcb_web_auth.urls')),
    url(r'^api/v1/', include('d4s2_api_v1.urls')),
    url(r'^api/v2/', include('d4s2_api_v2.urls')),
    url(r'^api/v3/', include('d4s2_api_v3.urls')),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^api-auth-token/', authtoken_views.obtain_auth_token),
    url(r'^accounts/login/$', auth_views.login, {'template_name': 'gcb_web_auth/login.html' }, name='login'),
    url(r'^accounts/logout/$', auth_views.logout, {'template_name': 'gcb_web_auth/logged_out.html' }, name='logout'),
    url(r'^accounts/login-local/$', auth_views.login, {'template_name': 'gcb_web_auth/login-local.html'}, name='login-local'),
    # Redirect / to /accounts/login
    url(r'^$', RedirectView.as_view(pattern_name='auth-home', permanent=False)),
]
