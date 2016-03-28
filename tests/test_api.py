import os
import unittest
import tempfile
import json
from handover_api import app, models, schemas


class ApiTestCase(unittest.TestCase):
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


class HandoverResourceTestCase(ApiTestCase):

    def testEmptyList(self):
        rv = self.client.get('/handovers/')
        payload = json.loads(rv.data)
        self.assertEqual(len(payload['results']), 0)

    def testNotFound(self):
        rv = self.client.get('/handovers/131')
        self.assertEqual(rv.status_code, 404)

    def createHandover(self, project_id, from_user, to_user):
        h = models.HandoverModel(project_id, from_user, to_user)
        self.session.add(h)
        self.session.commit()

    def countHandovers(self):
        return len(models.HandoverModel.query.all())

    def testGetHandover(self):
        self.createHandover('project-id-1','from', 'to')
        rv = self.client.get('/handovers/1')
        self.assertEqual(rv.status_code, 200)

    def testPostHandover(self):
        handover = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        self.assertEqual(rv.status_code, 201) # CREATED
        self.assertIn('Initiated', rv.data) # Initial state should be initiated

    def testPostHandoverDuplicate(self):
        handover = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        self.assertEqual(rv.status_code, 201) # CREATED
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        self.assertEqual(rv.status_code, 400) # Bad request

    def testPutHandover(self):
        handover = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/handovers/', headers=self.headers, data=json.dumps(handover))
        self.assertNotIn('user2', rv.data)
        handover['from_user_id'] = 'user2'
        rv = self.client.put('/handovers/1', headers=self.headers, data=json.dumps(handover))
        self.assertEqual(rv.status_code, 200)
        self.assertIn('user2',rv.data)

    def testDeleteHandover(self):
        self.createHandover('project-id-abc','frank','tom')
        self.assertEqual(self.countHandovers(), 1)
        rv = self.client.delete('/handovers/1', headers=self.headers)
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(self.countHandovers(), 0)

    def testFailDeleteHandover(self):
        rv = self.client.delete('/handovers/1', headers=self.headers)
        self.assertEqual(rv.status_code, 404)


class HandoverSchemaTestCase(ApiTestCase):

    def testDeserialize(self):
        handover_dict = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        schema = schemas.HandoverSchema()
        deserialized = schema.load(handover_dict)
        handover = deserialized.data
        self.assertEqual(handover.project_id, 'project-id-2')
        self.assertEqual(handover.from_user_id, 'user1')
        self.assertEqual(handover.to_user_id, 'user2')

class UserResourceTestCase(ApiTestCase):

    def testEmptyList(self):
        rv = self.client.get('/users/')
        payload = json.loads(rv.data)
        self.assertEqual(len(payload['results']), 0)

    def testNotFound(self):
        rv = self.client.get('/users/131')
        self.assertEqual(rv.status_code, 404)

    def createUser(self, dds_id, api_key):
        u = models.UserModel(dds_id, api_key)
        self.session.add(u)
        self.session.commit()

    def countUsers(self):
        return len(models.UserModel.query.all())

    def testGetUser(self):
        self.createUser('abcd1234','bbbbcvd')
        rv = self.client.get('/users/1')
        self.assertEqual(rv.status_code, 200)

    def testPostUser(self):
        user = {'dds_id': 'abaca22d2d', 'api_key': 'bzrwski124141' }
        rv = self.client.post('/users/', headers=self.headers, data=json.dumps(user))
        self.assertEqual(rv.status_code, 201) # CREATED

    def testPostUserDuplicate(self):
        user = {'dds_id': 'abaca22d2d', 'api_key': 'bzrwski124141' }
        rv = self.client.post('/users/', headers=self.headers, data=json.dumps(user))
        self.assertEqual(rv.status_code, 201) # CREATED
        rv = self.client.post('/users/', headers=self.headers, data=json.dumps(user))
        self.assertEqual(rv.status_code, 400) # Bad request

    def testPutUser(self):
        user = {'dds_id': 'abaca22d2d', 'api_key': 'api_key_value_1' }
        rv = self.client.post('/users/', headers=self.headers, data=json.dumps(user))
        self.assertNotIn('api_key_value_2', rv.data)
        user['api_key'] = 'api_key_value_2'
        rv = self.client.put('/users/1', headers=self.headers, data=json.dumps(user))
        self.assertEqual(rv.status_code, 200)
        self.assertIn('api_key_value_2',rv.data)

    def testDeleteUser(self):
        self.createUser('abcd1234','bbbbcvd')
        self.assertEqual(self.countUsers(), 1)
        rv = self.client.delete('/users/1', headers=self.headers)
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(self.countUsers(), 0)

    def testFailDeleteUser(self):
        rv = self.client.delete('/users/1', headers=self.headers)
        self.assertEqual(rv.status_code, 404)


class DraftResourceTestCase(ApiTestCase):

    def testEmptyList(self):
        rv = self.client.get('/drafts/')
        payload = json.loads(rv.data)
        self.assertEqual(len(payload['results']), 0)

    def testNotFound(self):
        rv = self.client.get('/drafts/131')
        self.assertEqual(rv.status_code, 404)

    def createDraft(self, project_id, from_user, to_user):
        h = models.DraftModel(project_id, from_user, to_user)
        self.session.add(h)
        self.session.commit()

    def countDrafts(self):
        return len(models.DraftModel.query.all())

    def testGetDraft(self):
        self.createDraft('project-id-1','from', 'to')
        rv = self.client.get('/drafts/1')
        self.assertEqual(rv.status_code, 200)

    def testPostDraft(self):
        draft = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        rv = self.client.post('/drafts/', headers=self.headers, data=json.dumps(draft))
        self.assertEqual(rv.status_code, 201) # CREATED
        self.assertIn('Notified', rv.data) # Initial state should be notified

    def testPostDraftDuplicate(self):
        draft = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/drafts/', headers=self.headers, data=json.dumps(draft))
        self.assertEqual(rv.status_code, 201) # CREATED
        rv = self.client.post('/drafts/', headers=self.headers, data=json.dumps(draft))
        self.assertEqual(rv.status_code, 400) # Bad request

    def testPutDraft(self):
        draft = {'project_id':'project-id-1', 'from_user_id': 'me', 'to_user_id': 'you'}
        rv = self.client.post('/drafts/', headers=self.headers, data=json.dumps(draft))
        self.assertNotIn('user2', rv.data)
        draft['from_user_id'] = 'user2'
        rv = self.client.put('/drafts/1', headers=self.headers, data=json.dumps(draft))
        self.assertEqual(rv.status_code, 200)
        self.assertIn('user2',rv.data)

    def testDeleteDraft(self):
        self.createDraft('project-id-abc','frank','tom')
        self.assertEqual(self.countDrafts(), 1)
        rv = self.client.delete('/drafts/1', headers=self.headers)
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(self.countDrafts(), 0)

    def testFailDeleteDraft(self):
        rv = self.client.delete('/drafts/1', headers=self.headers)
        self.assertEqual(rv.status_code, 404)


if __name__ == '__main__':
    unittest.main()
