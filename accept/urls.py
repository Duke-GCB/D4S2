from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.accept, name='accept-index'),
    url(r'^process/$', views.accept_process, name='accept-process'),
    url(r'^reject/$', views.handover_reject, name='handover-reject'),
]
