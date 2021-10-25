# given a user list their projects
# given a user and a name get a project
# reads both DDS and New projects
from switchboard.dds_util import DDSUtil, DDSProject


class Backend(object):
    dds = "dds"
    azure = "azure"


class Project(object):
    def __init__(self, id, name, url, created_on, last_updated_on, backend):
        self.id = id
        self.name = name
        self.url = url
        self.created_on = created_on
        self.last_updated_on = last_updated_on
        self.backend = backend



def get_projects_for_user(user):
    projects = get_dds_projects_for_user(user)
    return projects


def get_dds_projects_for_user(user):
    dds_util = DDSUtil(user)
    return DDSProject.fetch_list(dds_util)


def get_azure_projects_for_user(user):
    return [
        Project("seqcore/Mouse", "seqcore/Mouse", "google.com", "")
    ]



def get_project_for_user(user, pk):
    dds_util = DDSUtil(user)
    DDSProject.fetch_one(dds_util, pk)


