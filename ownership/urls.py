from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.ownership_prompt, name='ownership-prompt'),
    url(r'^process/$', views.ownership_process, name='ownership-process'),
    url(r'^decline/$', views.ownership_decline, name='ownership-decline'),
]
