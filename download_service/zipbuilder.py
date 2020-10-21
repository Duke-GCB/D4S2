from zipstream import ZipFile
from ddsc.sdk.client import PathToFiles
from ddsc.core.ddsapi import DataServiceError
from ddsc.core.download import SWIFT_EXPIRED_STATUS_CODE, S3_EXPIRED_STATUS_CODE
import requests


def is_expired_dds_response(response):
    """
    Check status_code of the response for the two values denoting expired URLs
    :param response: requests.Response
    :return: bool: True when the response is expired status
    """
    return response.status_code == SWIFT_EXPIRED_STATUS_CODE or response.status_code == S3_EXPIRED_STATUS_CODE


class ZipBuilderException(BaseException):
    def __init__(self, message):
        self.message = message


class NotFoundException(ZipBuilderException):
    pass


class NotSupportedException(ZipBuilderException):
    pass


class DDSZipBuilder(object):
    """
    Builds a zip file as a stream, containing all the files in a DukeDS project.
    """

    def __init__(self, project_id, client):
        """
        :param project_id: The id of a DukeDS project
        :param client: A ddsc.sdk.Client instance ready to make API calls
        """
        self.project_id = project_id
        self.client = client
        self.page_size = client.dds_connection.config.page_size

    @staticmethod
    def _handle_dataservice_error(e, message):
        if e.status_code == 404:
            raise NotFoundException(message)
        else:
            raise

    def get_project_name(self):
        """
        Uses the client to look up the project name from DukeDS
        :return: str: project name
        """
        try:
            project = self.client.get_project_by_id(self.project_id)
            return project.name
        except DataServiceError as e:
            DDSZipBuilder._handle_dataservice_error(e, 'Project {} not found'.format(self.project_id))

    def get_filename(self):
        """
        Generates a file name for the zip file based on the project name
        :return: str: file name ending in .zip
        """
        project_name = self.get_project_name()
        return '{}.zip'.format(project_name)

    def raise_on_filename_mismatch(self, filename):
        """
        Raises a NotFoundException if the supplied filename does not match this builder's
        generated filename (should be project_name + '.zip'

        :param filename: str: The file name to compare
        """
        expected_filename = self.get_filename()
        if filename != expected_filename:
            raise NotFoundException('Project {} not found'.format(self.project_id))

    def get_project_file_generator(self):
        """
        Returns a generator that returns DukeDS files for the current project including a download url
        :return: generator yielding ddsc.core.remotestore.ProjectFile, requests.Response.headers tuples
        """
        try:
            project = self.client.get_project_by_id(self.project_id)
            return project.get_project_files_generator(page_size=self.page_size)
        except DataServiceError as e:
            DDSZipBuilder._handle_dataservice_error(e, 'Project {} not found'.format(self.project_id))

    def get_url(self, file_id):
        """
        Generate a file download URL for a DDS file id. This URL will be signed with an
        expiration date, so this method should only be called right before the URL will be fetched.
        :param file_id: str: DDS file id
        :return: The URL string to GET.
        """
        try:
            file_download = self.client.dds_connection.get_file_download(file_id)
            if file_download.http_verb == 'GET':
                return '{}{}'.format(file_download.host, file_download.url)
            else:
                raise NotSupportedException('This file requires an unsupported download method: {}'.format(file_download.http_verb))
        except DataServiceError as e:
            DDSZipBuilder._handle_dataservice_error(e, 'File with id {} not found'.format(file_id))

    def fetch(self, project_file):
        """
        Generator to provide the contents of the DDS file using requests.get with a streaming response.
        :param project_file: ddsc.core.remotestore.ProjectFile containing file info and a potentially expired url
        :return: generator, bytes of the DDS file fetched from its URL.
        """
        # Due to the specifics of how python generators work, we have to make sure the yield appears in the same
        # function as the call to self.get_url()
        url = project_file.file_url['host'] + project_file.file_url['url']
        response = requests.get(url, stream=True)
        if is_expired_dds_response(response):
            url = self.get_url(project_file.id)
            response = requests.get(url, stream=True)
        response.raise_for_status()
        for chunk in response.raw.stream():
            yield chunk

    def build_streaming_zipfile(self):
        """
        Make a generator that, when consumed, fetches DDS file contents on demand using zipstream.ZipFile's
        write_iter method.
        :return: a zipstream.ZipFile with the contents
        """
        # Set allowZip64 explicitly - it normally looks at file size but since we're building on the fly
        # we don't know that ahead of time
        zipfile = ZipFile(allowZip64=True)
        for project_file, _ in self.get_project_file_generator():
            # Must provide buffer_size so that write_iter will know to use zip64
            zipfile.write_iter(project_file.path, self.fetch(project_file), buffer_size=project_file.size)
            yield from zipfile.flush()
        yield from zipfile
