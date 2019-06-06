from django.conf.urls import url
from download_service import views

urlpatterns = [
    url(r'^dds-projects/(?P<project_id>.+)/(?P<filename>.+\.zip)$', views.dds_project_zip, name='download-dds-project-zip'),
]
