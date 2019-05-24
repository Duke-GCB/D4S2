from django.test.testcases import TestCase
from download_service.zipbuilder import DDSZipBuilder
from ddsc.sdk.client import Client, File, FileDownload, Project, DDSConnection
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
        mock_children = [Mock(), Mock()]
        self.mock_client.dds_connection.get_project_children.return_value = mock_children
        builder = DDSZipBuilder(self.project_id, self.mock_client)
        dds_paths = builder.get_dds_paths()
        # get_project_children should be called with the project id
        self.assertEqual(self.mock_client.dds_connection.get_project_children.call_args, call(self.project_id))
        # PathToFiles().add_paths_for_children_of_node should be called with each child
        self.assertEqual(mock_path_to_files.return_value.add_paths_for_children_of_node.mock_calls, [
            call(mock_children[0]),
            call(mock_children[1])
        ])
        self.assertEqual(dds_paths, mock_path_to_files.return_value.paths)

    def test_get_url(self):
        mock_file_download = create_autospec(FileDownload, host='http://example.org', url='/path/file.ext')
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

    def test_call_order(self):
        pass

