class MockDDSUser(object):
    def __init__(self, full_name, email):
        self.full_name = full_name
        self.email = email


class MockDDSProject(object):
    def __init__(self, name):
        self.name = name
        self.children = []


