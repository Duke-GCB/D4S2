from zipstream import ZipFile
from ddsc.sdk.client import PathToFiles
from ddsc.core.ddsapi import DataServiceError
import requests


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
    Notes about generators and timeliness
    """

    def __init__(self, project_id, client):
        """

        :param project_id: The id of a DukeDS project
        :param client: A ddsc.sdk.Client instance ready to make API calls
        """
        self.project_id = project_id
        self.client = client

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

    def get_dds_paths(self):
        """
        Builds a mapping of file paths (strings) in the dds project to ddsc.sdk.client.File objects
        :return: OrderedDict where keys are relative paths in the project and values are ddsc.sdk.client.File objects
        """
        try:
            children = self.client.dds_connection.get_project_children(self.project_id)
            ptf = PathToFiles()
            for child in children:
                ptf.add_paths_for_children_of_node(child)
            return ptf.paths  # OrderedDict of path -> File
        except DataServiceError as e:
            DDSZipBuilder._handle_dataservice_error(e, 'Project {} not found'.format(self.project_id))

    def get_url(self, dds_file):
        """
        Uses the client to get a download URL for a ddsc.sdk.client.File object. This URL will be signed with an
        expiration date, so this method should only be called right before the URL will be fetched.

        :param dds_file: A ddsc.sdk.client.File object for which to get a URL
        :return: The URL string to GET.
        """
        # This is a time-sensitive call, so we should only do it right before fetch
        try:
            file_download = self.client.dds_connection.get_file_download(dds_file.id)
            if file_download.http_verb == 'GET':
                return '{}{}'.format(file_download.host, file_download.url)
            else:
                raise NotSupportedException('This file requires an unsupported download method: {}'.format(file_download.http_verb))
        except DataServiceError as e:
            DDSZipBuilder._handle_dataservice_error(e, 'File with id {} not found'.format(dds_file.id))

    def fetch(self, dds_file):
        """
        Generator to provide the contents of the DDS file using requests.get with a streaming response.

        Note: Since self.get_url() returns a URL that will expire, it's critical that the yield and the get_url()
        call appear in the same function. The 'yield' in this function actually causes the get_url() call to be deferred
        until the first time the generator is consumed. If the yield were in a nested function, get_url() would be
        called immediately and the URL could easily expire before it's fetched.

        :param dds_file: A ddsc.sdk.client.File object to fetch
        :return: generator, bytes of the DDS file fetched from its URL.
        """
        # Due to the specifics of how python generators work, we have to make sure the yield appears in the same
        # function as the call to self.get_url().
        url = self.get_url(dds_file)
        response = requests.get(url, stream=True)
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
        paths = self.get_dds_paths()
        for (filename, dds_file) in paths.items():
            # Must provide buffer_size so that write_iter will know to use zip64
            file_size = dds_file.current_version['upload']['size']
            zipfile.write_iter(filename, self.fetch(dds_file), buffer_size=file_size)
        return zipfile


