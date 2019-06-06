from django.http import StreamingHttpResponse, HttpResponseServerError
from download_service.zipbuilder import DDSZipBuilder, NotFoundException, NotSupportedException
from django.contrib.auth.decorators import login_required
from download_service.utils import make_client
from django.http import Http404


@login_required
def dds_project_zip(request, project_id, filename):
    client = make_client(request.user)
    builder = DDSZipBuilder(project_id, client)
    try:
        builder.raise_on_filename_mismatch(filename)
        response = StreamingHttpResponse(builder.build_streaming_zipfile(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        return response
    except NotFoundException as e:
        raise Http404(e.message)
    except NotSupportedException as e:
        return HttpResponseServerError(content=e.message)
