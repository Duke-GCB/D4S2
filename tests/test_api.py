import os
import unittest
import tempfile
import json
from handover_api import app, models, schemas


class HandoverApiTestCase(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.database_file = tempfile.mkstemp()
        app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://' + self.database_file
        self.app = app.app.test_client()
        db = models.db
        db.create_all()
        self.session = db.session

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.database_file)


class HandoverResourceTestCase(HandoverApiTestCase):

    def testEmptyList(self):
        rv = self.app.get('/handovers/')
        payload = json.loads(rv.data)
        assert len(payload['results']) == 0

    def testNotFound(self):
        rv = self.app.get('/handovers/131')
        assert "handover 131 doesn't exist" in rv.data
        assert rv.status_code == 404

    def createHandover(self, project_id, from_user, to_user):
        h = models.HandoverModel(project_id, from_user, to_user)
        self.session.add(h)
        self.session.commit()

    def testGetHandover(self):
        self.createHandover('project-id-1','from', 'to')
        rv = self.app.get('/handovers/1')
        assert rv.status_code == 200

    def testPostHandover(self):
        handover = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        rv = self.app.post('/handovers/',data=json.dumps(handover))
        assert rv.status_code == 201 # CREATED

class HandoverSchemaTestCase(HandoverApiTestCase):

    def testDeserialize(self):
        handover_dict = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        schema = schemas.HandoverSchema()
        deserialized = schema.load(handover_dict)
        handover = deserialized.data
        self.assertEqual(handover.project_id, 'project-id-2')
        self.assertEqual(handover.from_user_id, 'user1')
        self.assertEqual(handover.to_user_id, 'user2')

if __name__ == '__main__':
    unittest.main()
