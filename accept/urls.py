from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.accept, name='accept-index'),
    url(r'^process/$', views.handover_process, name='handover-accept'),
    url(r'^reject/$', views.handover_reject, name='handover-reject'),
]
