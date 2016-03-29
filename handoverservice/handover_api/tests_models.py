from django.db import IntegrityError
from django.test import TestCase
from handover_api.models import User, Handover, Draft, State


class HandoverTestCase(TestCase):

    def setUp(self):
        Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')

    def test_initial_state(self):
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.INITIATED, 'New handovers should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(IntegrityError):
            Handover.objects.create(project_id=None, from_user_id=None, to_user_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')


class DraftTestCase(TestCase):

    def setUp(self):
        Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')

    def test_initial_state(self):
        draft = Draft.objects.first()
        self.assertEqual(draft.state, State.NOTIFIED, 'New drafts should be in notified state')

    def test_required_fields(self):
        with self.assertRaises(IntegrityError):
            Draft.objects.create(project_id=None, from_user_id=None, to_user_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')


class UserTestCase(TestCase):

    def setUp(self):
        User.objects.create(dds_id='abcd-1234-fghi-5678', api_key='zxxsdvasv//aga')

    def test_required_fields_dds_id(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(dds_id=None, api_key='gwegwg')

    def test_required_fields_api_key(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(dds_id='fefwef', api_key=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(dds_id='abcd-1234-fghi-5678', api_key='fwmp2392')

