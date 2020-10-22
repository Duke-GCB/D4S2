from django.test.testcases import TestCase
from download_service.zipbuilder import DDSZipBuilder, NotFoundException, NotSupportedException
from ddsc.sdk.client import Client, File, FileDownload, Project, DDSConnection
from ddsc.core.ddsapi import DataServiceError
from requests import Response
from unittest.mock import Mock, patch, create_autospec, PropertyMock, call, ANY
from collections import OrderedDict


class DDSZipBuilderTestCase(TestCase):

    @staticmethod
    def mock_project_with_name(name):
        mock_project = create_autospec(Project)
        name_property = PropertyMock(return_value=name)
        type(mock_project).name = name_property
        return mock_project

    def setUp(self):
        self.mock_client = create_autospec(Client)
        self.mock_client.dds_connection = create_autospec(DDSConnection)
        self.mock_client.dds_connection.config = Mock(page_size=100)
        self.project_id = '514d0f77-a167-400d-8466-3043428029fe'
        self.project_file1 = Mock(size=100, path='file1.txt', file_url={'host':'somehost', 'url':'/file1.txt'})
        self.project_file1.id = '123'
        self.project_file2 = Mock(size=200, path='file2.txt', file_url={'host':'somehost', 'url':'/file2.txt'})
        self.project_file2.id = '456'

    def test_init(self):
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        self.assertEqual(builder.project_id, self.project_id)
        self.assertEqual(builder.client, self.mock_client)

    def test_get_project_name(self):
        mock_project = DDSZipBuilderTestCase.mock_project_with_name('ProjectABC')
        self.mock_client.get_project_by_id.return_value = mock_project
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        self.assertEqual(builder.get_project_name(), 'ProjectABC')

    def test_get_filename(self):
        mock_project = DDSZipBuilderTestCase.mock_project_with_name('project-xyz')
        self.mock_client.get_project_by_id.return_value = mock_project
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        self.assertEqual(builder.get_filename(), 'project-xyz.zip')

    @patch('download_service.zipbuilder.PathToFiles')
    def test_get_project_file_generator(self, mock_path_to_files):
        mock_project = DDSZipBuilderTestCase.mock_project_with_name('project-xyz')
        self.mock_client.get_project_by_id.return_value = mock_project
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        result = builder.get_project_file_generator()
        self.assertEqual(result, mock_project.get_project_files_generator.return_value)
        mock_project.get_project_files_generator.assert_called_with(page_size=100)

    def test_get_url(self):
        mock_file_download = create_autospec(FileDownload, host='http://example.org', url='/path/file.ext', http_verb='GET')
        mock_get_file_download = self.mock_client.dds_connection.get_file_download
        mock_get_file_download.return_value = mock_file_download
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        url = builder.get_url(file_id='1234')
        # Get file download should have been called with the file id
        self.assertEqual(mock_get_file_download.call_args, call('1234'))
        # Built URL should be assembled from the properties of the mock_file_download
        self.assertEqual(url, 'http://example.org/path/file.ext')

    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    def test_fetch_chunks(self, mock_get_url, mock_requests_get):
        mock_chunks = ['chunk1','chunk2','chunk3']
        url = 'https://example.org/path/file.ext'
        mock_response = create_autospec(Response)
        mock_response.status_code = 403
        mock_requests_get.return_value = mock_response
        mock_response.raw = Mock(stream=Mock(return_value=mock_chunks))
        mock_get_url.return_value = url
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        mock_project_file = Mock(
            file_url={'host':'somehost', 'url': '/file1.txt'},
        )
        mock_project_file.id = '123'
        fetched = builder.fetch(mock_project_file)
        self.assertEqual(list(fetched), mock_chunks)

        # try "expired" url then try url returned from get_url
        mock_requests_get.assert_has_calls([
            call('somehost/file1.txt', stream=True),
            call('https://example.org/path/file.ext', stream=True),
        ])

        # get_url should be called with the file
        mock_get_url.assert_called_with('123')

    @patch('download_service.zipbuilder.ZipFile')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_project_file_generator')
    @patch('download_service.zipbuilder.DDSZipBuilder.fetch')
    def test_build_streaming_zipfile(self, mock_fetch, mock_get_project_file_generator, mock_zipfile):
        mock_get_project_file_generator.return_value = iter(
            [
                (self.project_file1, None),
                (self.project_file2, None),
            ]
        )
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        list(builder.build_streaming_zipfile())

        # check zipfile added with appropriate files
        mock_zipfile.return_value.write_iter.assert_has_calls([
            call('file1.txt', mock_fetch.return_value, buffer_size=100),
            call('file2.txt', mock_fetch.return_value, buffer_size=200),
        ])

    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_project_file_generator')
    @patch('download_service.zipbuilder.is_expired_dds_response')
    def test_call_order(self, mock_is_expired_dds_response, mock_get_project_file_generator, mock_get_url,
                        mock_requests_get):
        """
        Test the correct call order when streaming the zip file.
        Example uses a 2 file project
        """
        mock_is_expired_dds_response.return_value = False

        manager = Mock()
        manager.attach_mock(mock_get_url, 'get_url')
        manager.attach_mock(mock_requests_get, 'requests_get')
        manager.attach_mock(mock_requests_get.return_value.raw.stream, 'response_stream')
        manager.attach_mock(mock_get_project_file_generator, 'get_project_file_generator')

        mock_get_project_file_generator.return_value = iter(
            [
                (self.project_file1, None),
                (self.project_file2, None),
            ]
        )
        mock_requests_get.return_value.raw.stream.return_value = []

        builder = DDSZipBuilder(self.project_id, self.mock_client)
        streaming_zipfile = builder.build_streaming_zipfile()
        # Iterate through the generator
        for zipfile_data in streaming_zipfile:
            list(zipfile_data)

        # After iterating, call order should be
        #
        # 1. get_project_file_generator - Get project files
        # 2. requests_get - Begin retrieval of data for file 1
        # 3. requests_get.raise_for_status - verify the response was good
        # 4. response_stream - Get response stream generator for file 1
        # 5. requests_get - Begin retrieval of data for file 2
        # 6. requests_get.raise_for_status - verify the response was good
        # 7. response_stream - Get response stream generator for file 2

        expected_calls = [
            call.get_project_file_generator(),
            call.requests_get('somehost/file1.txt', stream=True),
            call.requests_get().raise_for_status(),
            call.response_stream(),
            call.requests_get('somehost/file2.txt', stream=True),
            call.requests_get().raise_for_status(),
            call.response_stream()
        ]
        manager.assert_has_calls(expected_calls)


    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_project_file_generator')
    @patch('download_service.zipbuilder.is_expired_dds_response')
    def test_call_order_one_expired(self, mock_is_expired_dds_response, mock_get_project_file_generator, mock_get_url,
                        mock_requests_get):
        """
        Test the correct call order when streaming the zip file where the first file has an expired URL
        Example uses a 2 file project
        """
        mock_is_expired_dds_response.side_effect = [
            True,
            False
        ]

        manager = Mock()
        manager.attach_mock(mock_get_url, 'get_url')
        manager.attach_mock(mock_requests_get, 'requests_get')
        manager.attach_mock(mock_requests_get.return_value.raw.stream, 'response_stream')
        manager.attach_mock(mock_get_project_file_generator, 'get_project_file_generator')

        mock_get_project_file_generator.return_value = iter(
            [
                (self.project_file1, None),
                (self.project_file2, None),
            ]
        )
        mock_requests_get.return_value.raw.stream.return_value = []

        builder = DDSZipBuilder(self.project_id, self.mock_client)
        streaming_zipfile = builder.build_streaming_zipfile()
        # Iterate through the generator
        for zipfile_data in streaming_zipfile:
            list(zipfile_data)

        # After iterating, call order should be
        #
        # 1. get_project_file_generator - Get project files
        # 2. requests_get - Begin retrieval of data for file 1
        # 3. get_url - Fetch url since URL was expired
        # 4. requests_get - Begin retrieval of new URL for file 1
        # 5. requests_get.raise_for_status - verify the response was good
        # 6. response_stream - Get response stream generator for file 1
        # 7. requests_get - Begin retrieval of data for file 2
        # 8. requests_get.raise_for_status - verify the response was good
        # 9. response_stream - Get response stream generator for file 2

        expected_calls = [
            call.get_project_file_generator(),
            call.requests_get('somehost/file1.txt', stream=True),
            call.get_url('123'),
            call.requests_get(mock_get_url.return_value, stream=True),
            call.requests_get().raise_for_status(),
            call.response_stream(),
            call.requests_get('somehost/file2.txt', stream=True),
            call.requests_get().raise_for_status(),
            call.response_stream()
        ]
        manager.assert_has_calls(expected_calls)

class MockDataServiceError(DataServiceError):

    def __init__(self, status_code):
        self.status_code = status_code


class DDSZipBuilderExceptionsTestCase(TestCase):

    def setUp(self):
        self.mock_client = create_autospec(Client)
        self.mock_client.dds_connection = create_autospec(DDSConnection)
        self.mock_client.dds_connection.config = Mock(page_size=100)
        self.project_id = 'abc'
        self.file_id = '123'
        self.mock_dds_file = create_autospec(File, id=self.file_id)
        self.builder = DDSZipBuilder(self.project_id, self.mock_client)

    def test_get_project_name_catches_dataservice_404_raises_not_found(self):
        self.mock_client.get_project_by_id.side_effect = MockDataServiceError(404)
        with self.assertRaisesMessage(NotFoundException, "Project abc not found"):
            self.builder.get_project_name()

    def test_get_project_name_raises_other_dataservice_errors(self):
        self.mock_client.get_project_by_id.side_effect = MockDataServiceError(500)
        with self.assertRaises(DataServiceError):
            self.builder.get_project_name()

    def test_get_dds_paths_catches_dataservice_404_raises_not_found(self):
        self.mock_client.get_project_by_id.side_effect = MockDataServiceError(404)
        with self.assertRaisesMessage(NotFoundException, "Project abc not found"):
            self.builder.get_project_file_generator()

    def test_get_dds_paths_raises_other_dataservice_errors(self):
        self.mock_client.get_project_by_id.side_effect = MockDataServiceError(500)
        with self.assertRaises(DataServiceError):
            self.builder.get_project_file_generator()

    def test_get_url_checks_http_verb_raises_not_supported(self):
        self.mock_client.dds_connection.get_file_download.return_value = create_autospec(FileDownload, http_verb='POST')
        with self.assertRaisesMessage(NotSupportedException, 'This file requires an unsupported download method: POST'):
            self.builder.get_url(self.mock_dds_file)

    def test_get_url_catches_dataservice_404_raises_not_found(self):
        self.mock_client.dds_connection.get_file_download.side_effect = MockDataServiceError(404)
        with self.assertRaisesMessage(NotFoundException, "File with id 123 not found"):
            self.builder.get_url(file_id='123')

    def test_get_url_raises_other_dataservice_errors(self):
        self.mock_client.dds_connection.get_file_download.side_effect = MockDataServiceError(500)
        with self.assertRaises(DataServiceError):
            self.builder.get_url(self.mock_dds_file)

    @patch('download_service.zipbuilder.DDSZipBuilder.get_filename')
    def test_raise_on_filename_mismatch_raises(self, mock_get_filename):
        mock_get_filename.return_value = 'file1.zip'
        with self.assertRaisesMessage(NotFoundException, 'Project abc not found'):
            self.builder.raise_on_filename_mismatch('file2.zip')

    @patch('download_service.zipbuilder.DDSZipBuilder.get_filename')
    def test_raise_on_filename_mismatch_ok(self, mock_get_filename):
        mock_get_filename.return_value = 'file1.zip'
        self.builder.raise_on_filename_mismatch('file1.zip')
