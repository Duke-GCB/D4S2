import os
import unittest
import tempfile
import json
from handover_api import app, models, schemas


class HandoverApiTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.database_file = tempfile.mkstemp()
        handover_api = app.create_app('sqlite:///' + self.database_file)
        self.client = handover_api.test_client()
        models.db.create_all()
        self.session = models.db.session
        self.headers = {'content-type': 'application/json'}


    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.database_file)


class HandoverResourceTestCase(HandoverApiTestCase):

    def testEmptyList(self):
        rv = self.client.get('/handovers/')
        payload = json.loads(rv.data)
        assert len(payload['results']) == 0

    def testNotFound(self):
        rv = self.client.get('/handovers/131')
        assert "handover 131 doesn't exist" in rv.data
        assert rv.status_code == 404

    def createHandover(self, project_id, from_user, to_user):
        h = models.HandoverModel(project_id, from_user, to_user)
        self.session.add(h)
        self.session.commit()

    def countHandovers(self):
        return len(models.HandoverModel.query.all())

    def testGetHandover(self):
        self.createHandover('project-id-1','from', 'to')
        rv = self.client.get('/handovers/1')
        assert rv.status_code == 200

    def testPostHandover(self):
        handover = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        assert rv.status_code == 201 # CREATED

    def testPostHandoverDuplicate(self):
        handover = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        assert rv.status_code == 201 # CREATED
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        assert rv.status_code == 400 # Bad request

    def testPutHandover(self):
        handover = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        assert "user2" not in rv.data
        handover['from_user_id'] = 'user2'
        rv = self.client.put('/handovers/1', headers=self.headers, data=json.dumps(handover))
        assert rv.status_code == 200
        assert "user2" in rv.data

    def testDeleteHandover(self):
        self.createHandover('project-id-abc','frank','tom')
        self.assertEqual(self.countHandovers(), 1)
        rv = self.client.delete('/handovers/1', headers=self.headers)
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(self.countHandovers(), 0)


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
