from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api/v1/', include('handover_api.urls')),
    url(r'^$', RedirectView.as_view(url='/api/v1/'))
]
