from django.test.testcases import TestCase
from download_service.zipbuilder import DDSZipBuilder, NotFoundException, NotSupportedException
from ddsc.sdk.client import Client, File, FileDownload, Project, DDSConnection
from ddsc.core.ddsapi import DataServiceError
from requests import Response
from unittest.mock import Mock, patch, create_autospec, PropertyMock, call
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
        self.project_id = '514d0f77-a167-400d-8466-3043428029fe'

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
    def test_get_dds_paths(self, mock_path_to_files):
        mock_project = DDSZipBuilderTestCase.mock_project_with_name('project-xyz')
        self.mock_client.get_project_by_id.return_value = mock_project
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        dds_paths = builder.get_dds_paths()
        # get_project_by_id should be called with the project id
        self.assertEqual(self.mock_client.get_project_by_id.call_args, call(self.project_id))
        # PathToFiles().add_paths_for_children_of_node should be called with the project
        self.assertEqual(mock_path_to_files.return_value.add_paths_for_children_of_node.call_args, call(mock_project))
        self.assertEqual(dds_paths, mock_path_to_files.return_value.paths)

    def test_get_url(self):
        mock_file_download = create_autospec(FileDownload, host='http://example.org', url='/path/file.ext', http_verb='GET')
        mock_get_file_download = self.mock_client.dds_connection.get_file_download
        mock_get_file_download.return_value = mock_file_download
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        mock_file = create_autospec(File)
        mock_file.id = 'file-id'
        url = builder.get_url(mock_file)
        # Get file download should have been called with the file id
        self.assertEqual(mock_get_file_download.call_args, call('file-id'))
        # Built URL should be assembled from the properties of the mock_file_download
        self.assertEqual(url, 'http://example.org/path/file.ext')

    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    def test_fetch_chunks(self, mock_get_url, mock_requests_get):
        mock_chunks = ['chunk1','chunk2','chunk3']
        url = 'https://example.org/path/file.ext'
        mock_response = create_autospec(Response)
        mock_requests_get.return_value = mock_response
        mock_response.raw = Mock(stream=Mock(return_value=mock_chunks))
        mock_get_url.return_value = url
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        mock_file = create_autospec(File)
        fetched = builder.fetch(mock_file)
        self.assertEqual(list(fetched), mock_chunks)
        # get_url should be called with the file
        self.assertEqual(mock_get_url.call_args, call(mock_file))
        # requests_get should be called with the url and stream=True
        self.assertEqual(mock_requests_get.call_args, call(url, stream=True))

    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    def test_fetch_does_not_get_file_url_until_iterated(self, mock_get_url, mock_requests_get):
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        # Instantiating a DDSZipBuilder will not fetch any URLs yet
        self.assertFalse(mock_get_url.called)
        fetched = builder.fetch(create_autospec(File))
        # Invoking DDSZipBuilder.fetch() to get a generator must not call get_url
        self.assertFalse(mock_get_url.called)
        # Iterating on the generator will trigger the call
        for _ in fetched:
            pass
        self.assertTrue(mock_get_url.called)
        # Also requests.get should have been called
        self.assertTrue(mock_requests_get.called)

    @patch('download_service.zipbuilder.ZipFile')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_dds_paths')
    @patch('download_service.zipbuilder.DDSZipBuilder.fetch')
    def test_build_streaming_zipfile(self, mock_fetch, mock_get_dds_paths, mock_zipfile):
        mock_dds_files = OrderedDict({
            'file1.txt': create_autospec(File, current_version={'upload': {'size': 100}}),
            'file2.txt': create_autospec(File, current_version={'upload': {'size': 200}})
        })
        mock_get_dds_paths.return_value = mock_dds_files
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        streaming_zipfile = builder.build_streaming_zipfile()
        # it should call mock_get_dds_paths
        self.assertTrue(mock_get_dds_paths.called)
        # It should init a zipfile with allowZip64=true
        self.assertEqual(mock_zipfile.call_args, call(allowZip64=True))
        # it should call write_iter with filename, fetch results, and buffer size
        self.assertEqual(mock_zipfile.return_value.write_iter.mock_calls, [
            call('file1.txt', mock_fetch.return_value, buffer_size=100),
            call('file2.txt', mock_fetch.return_value, buffer_size=200),
        ])
        # It should call fetch for each dds file, in order
        self.assertEqual(mock_fetch.mock_calls, [
            call(mock_dds_files['file1.txt']),
            call(mock_dds_files['file2.txt'])
        ])
        # it should return the zip file
        self.assertEqual(streaming_zipfile, mock_zipfile.return_value)

    @patch('download_service.zipbuilder.requests.get')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_url')
    @patch('download_service.zipbuilder.DDSZipBuilder.get_dds_paths')
    def test_call_order(self, mock_get_dds_paths, mock_get_url, mock_requests_get):
        """
        Test the correct call order when streaming the zip file.
        Example uses a 2 file project
        """

        manager = Mock()
        manager.attach_mock(mock_get_url, 'get_url')
        manager.attach_mock(mock_requests_get, 'requests_get')
        manager.attach_mock(mock_requests_get.return_value.raw.stream, 'response_stream')
        manager.attach_mock(mock_get_dds_paths, 'get_dds_paths')

        mock_dds_files = OrderedDict({
            'file1.txt': create_autospec(File, current_version={'upload': {'size': 100}}),
            'file2.txt': create_autospec(File, current_version={'upload': {'size': 200}})
        })
        mock_get_dds_paths.return_value = mock_dds_files
        mock_requests_get.return_value.raw.stream.return_value = []

        builder = DDSZipBuilder(self.project_id, self.mock_client)
        streaming_zipfile = builder.build_streaming_zipfile()
        # Before iterating the only call that should be made is getting the paths
        self.assertEqual(manager.mock_calls, [call.get_dds_paths(), ])
        for _ in streaming_zipfile:
            pass

        # After iterating, call order should be
        #
        # 1. get_dds_paths - Get project paths
        # 2. get_url - Get download URL for file 1
        # 3. requests_get - Begin retrieval of data for file 1
        # 4. response_stream - Get response stream generator for file 1
        # 2. get_url - Get download URL for file 2
        # 3. requests_get - Begin retrieval of data for file 2
        # 4. response_stream - Get response stream generator for file 2

        expected_calls = [
            call.get_dds_paths(),
            call.get_url(mock_dds_files['file1.txt']),
            call.requests_get(mock_get_url.return_value, stream=True),
            call.response_stream(),
            call.get_url(mock_dds_files['file2.txt']),
            call.requests_get(mock_get_url.return_value, stream=True),
            call.response_stream(),
        ]
        self.assertEqual(manager.mock_calls, expected_calls)


class MockDataServiceError(DataServiceError):

    def __init__(self, status_code):
        self.status_code = status_code


class DDSZipBuilderExceptionsTestCase(TestCase):

    def setUp(self):
        self.mock_client = create_autospec(Client)
        self.mock_client.dds_connection = create_autospec(DDSConnection)
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
            self.builder.get_dds_paths()

    def test_get_dds_paths_raises_other_dataservice_errors(self):
        self.mock_client.get_project_by_id.side_effect = MockDataServiceError(500)
        with self.assertRaises(DataServiceError):
            self.builder.get_dds_paths()

    def test_get_url_checks_http_verb_raises_not_supported(self):
        self.mock_client.dds_connection.get_file_download.return_value = create_autospec(FileDownload, http_verb='POST')
        with self.assertRaisesMessage(NotSupportedException, 'This file requires an unsupported download method: POST'):
            self.builder.get_url(self.mock_dds_file)

    def test_get_url_catches_dataservice_404_raises_not_found(self):
        self.mock_client.dds_connection.get_file_download.side_effect = MockDataServiceError(404)
        with self.assertRaisesMessage(NotFoundException, "File with id 123 not found"):
            self.builder.get_url(self.mock_dds_file)

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
