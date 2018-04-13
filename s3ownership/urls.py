from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.ownership_prompt, name='s3ownership-prompt'),
    url(r'^process/$', views.ownership_process, name='s3ownership-process'),
    url(r'^decline/$', views.ownership_decline, name='s3ownership-decline'),
    url(r'^accepted/$', views.ownership_accepted, name='s3ownership-accepted'),
]
