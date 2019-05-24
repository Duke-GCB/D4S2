from django.http import StreamingHttpResponse
from download_service.zipbuilder import DDSZipBuilder
from ddsc.sdk.client import Client


def make_client():
    client = Client()  # This assumes it can authenticate
    return client


def dds_project_zip(request, project_id):
    client = make_client()
    builder = DDSZipBuilder(project_id, client)
    # this should trigger an exception if project not found
    filename = builder.get_filename()
    # what will this trigger if no access to project
    response = StreamingHttpResponse(builder.build_streaming_zipfile(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response
