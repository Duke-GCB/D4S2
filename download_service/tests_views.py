from django.core.urlresolvers import reverse
from django.test.testcases import SimpleTestCase
from unittest.mock import patch, call


@patch('download_service.views.make_client')
@patch('download_service.views.DDSZipBuilder')
class DDSProjectZipTestCase(SimpleTestCase):
    def setUp(self):
        self.project_id = 'abc-123'
        self.url = reverse('download-dds-project-zip', kwargs={'project_id': self.project_id})

    def test_built_url(self, mock_zip_builder, mock_make_client):
        self.assertEqual(self.url, '/download/dds-projects/abc-123.zip')

    def test_download_project_builds(self, mock_zip_builder, mock_make_client):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_zip_builder.call_args, call(self.project_id, mock_make_client.return_value))

    def test_response_content(self, mock_zip_builder, mock_make_client):
        mock_zip_builder.return_value.build.return_value = 'built zip content'
        response = self.client.get(self.url)
        self.assertContains(response, 'built zip content')

    def test_response_headers(self, mock_zip_builder, mock_make_client):
        mock_zip_builder.return_value.get_filename.return_value = 'ABC123.zip'
        response = self.client.get(self.url)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=ABC123.zip')
