from django.http import StreamingHttpResponse
from download_service.zipbuilder import DDSZipBuilder
from django.contrib.auth.decorators import login_required
from download_service.utils import make_client


@login_required
def dds_project_zip(request, project_id):
    client = make_client(request.user)
    builder = DDSZipBuilder(project_id, client)
    # this should trigger an exception if project not found
    filename = builder.get_filename()
    # what will this trigger if no access to project
    response = StreamingHttpResponse(builder.build_streaming_zipfile(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response
