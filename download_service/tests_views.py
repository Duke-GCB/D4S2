from django.core.urlresolvers import reverse
from django.test.testcases import TestCase
from unittest.mock import patch, call
from django.contrib.auth.models import User
from download_service.zipbuilder import NotFoundException


@patch('download_service.views.make_client')
@patch('download_service.views.DDSZipBuilder')
class DDSProjectZipTestCase(TestCase):
    def setUp(self):
        self.project_id = 'abc-123'
        self.url = reverse('download-dds-project-zip', kwargs={'project_id': self.project_id})
        username = 'download_user'
        password = 'secret'
        self.user = User.objects.create_user(username, password=password)
        self.client.login(username=username, password=password)

    def test_built_url(self, mock_zip_builder, mock_make_client):
        self.client.logout()
        self.assertEqual(self.url, '/download/dds-projects/abc-123.zip')

    def test_redirects_for_login(self, mock_zip_builder, mock_make_client):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('login') + '?next=/download/dds-projects/abc-123.zip')

    def test_download_project_builds(self, mock_zip_builder, mock_make_client):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_zip_builder.call_args, call(self.project_id, mock_make_client.return_value))

    def test_response_content(self, mock_zip_builder, mock_make_client):
        mock_zip_builder.return_value.build_streaming_zipfile.return_value = 'streaming zip content'
        response = self.client.get(self.url)
        self.assertContains(response, 'streaming zip content')

    def test_response_headers(self, mock_zip_builder, mock_make_client):
        mock_zip_builder.return_value.get_filename.return_value = 'ABC123.zip'
        response = self.client.get(self.url)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename=ABC123.zip')

    def test_404_if_project_not_found(self, mock_zip_builder, mock_make_client):
        mock_zip_builder.return_value.get_filename.side_effect = NotFoundException('not found')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
