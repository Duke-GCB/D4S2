from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ownership/', include('ownership.urls')),
    url(r'^api/v1/', include('d4s2_api.urls')),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    # login view is only used with local authentication. With production shibboleth config,
    # Apache will redirect to the shibboleth login page before django redirects to login.
    url(r'^accounts/login/$', auth_views.login, {'template_name': 'ownership/login.html' }),
    url(r'^accounts/logout/$', auth_views.logout, {'template_name': 'ownership/logged_out.html' }),
    url(r'^$', RedirectView.as_view(url='/api/v1/'))
]
