from mock import Mock

class MockDDSUser(object):
    def __init__(self, full_name, email):
        self.full_name = full_name
        self.email = email


class MockDDSProject(object):
    def __init__(self, name):
        self.name = name
        self.children = []

def setup_mock_handover_details(MockHandoverDetails):
    x = MockHandoverDetails()
    x.get_from_user.return_value = MockDDSUser('joe', 'joe@joe.com')
    x.get_to_user.return_value = MockDDSUser('bob', 'bob@joe.com')
    x.get_project.return_value = MockDDSProject('project')

def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = Mock()
    mock_ddsutil.return_value.get_remote_user = Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser('Test User', 'test@test.com')
    mock_ddsutil.return_value.get_remote_project.return_value = MockDDSProject('My Project')

