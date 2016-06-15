from django.db import IntegrityError
from django.test import TestCase
from handover_api.models import DukeDSUser, DukeDSProject, Handover, Draft, State


class HandoverTestCase(TestCase):
    HANDOVER_EMAIL_TEXT = 'handover email message'
    ACCEPT_EMAIL_TEXT = 'handover accepted'
    REJECT_EMAIL_TEXT = 'handover rejected'

    def setUp(self):
        self.project1 = DukeDSProject.objects.create(project_id='project1')
        self.user1 = DukeDSUser.objects.create(dds_id='user1')
        self.user2 = DukeDSUser.objects.create(dds_id='user2')
        Handover.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_initial_state(self):
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.NEW, 'New handovers should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(ValueError):
            Handover.objects.create(project=None, from_user=None, to_user=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Handover.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_token_autopopulate(self):
        handover = Handover.objects.first()
        self.assertIsNotNone(handover.token, 'token should default to a uuid')

    def test_mark_notified(self):
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.NEW)
        handover.mark_notified(HandoverTestCase.HANDOVER_EMAIL_TEXT)
        self.assertEqual(handover.state, State.NOTIFIED)

    def test_mark_accepted(self):
        performed_by = 'performer'
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.NEW)
        handover.mark_accepted(performed_by, HandoverTestCase.ACCEPT_EMAIL_TEXT)
        self.assertEqual(handover.state, State.ACCEPTED)
        self.assertEqual(handover.performed_by, performed_by)
        self.assertEqual(handover.completion_email_text, HandoverTestCase.ACCEPT_EMAIL_TEXT)

    def test_mark_rejected(self):
        performed_by = 'performer'
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.NEW)
        handover.mark_rejected(performed_by, 'Wrong person.',  HandoverTestCase.REJECT_EMAIL_TEXT)
        self.assertEqual(handover.state, State.REJECTED)
        self.assertEqual(handover.reject_reason, 'Wrong person.')
        self.assertEqual(handover.performed_by, performed_by)
        self.assertEqual(handover.completion_email_text, HandoverTestCase.REJECT_EMAIL_TEXT)

    def test_is_complete(self):
        handover = Handover.objects.first()
        self.assertEqual(handover.is_complete(), False)
        handover.mark_notified('')
        self.assertEqual(handover.is_complete(), False)
        handover.mark_accepted('','')
        self.assertEqual(handover.is_complete(), True)
        handover.mark_rejected('','','')
        self.assertEqual(handover.is_complete(), True)


class DraftTestCase(TestCase):

    def setUp(self):
        self.project1 = DukeDSProject.objects.create(project_id='project1')
        self.user1 = DukeDSUser.objects.create(dds_id='user1')
        self.user2 = DukeDSUser.objects.create(dds_id='user2')
        Draft.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_initial_state(self):
        draft = Draft.objects.first()
        self.assertEqual(draft.state, State.NEW, 'New drafts should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(ValueError):
            Draft.objects.create(project=None, from_user=None, to_user=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Draft.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_allows_multiple_drafts(self):
        user3 = DukeDSUser.objects.create(dds_id='user3')
        d = Draft.objects.create(project=self.project1, from_user=self.user1, to_user=user3)
        self.assertIsNotNone(d)


class ProjectTestCase(TestCase):
    def test_requires_project_id(self):
        with self.assertRaises(IntegrityError):
            DukeDSProject.objects.create(project_id=None)

    def test_create_project(self):
        p = DukeDSProject.objects.create(project_id='abcd-1234')
        self.assertIsNotNone(p)

class UserTestCase(TestCase):
    def setUp(self):
        DukeDSUser.objects.create(dds_id='abcd-1234-fghi-5678', api_key='zxxsdvasv//aga')

    def test_required_fields_dds_id(self):
        with self.assertRaises(IntegrityError):
            DukeDSUser.objects.create(dds_id=None, api_key='gwegwg')

    def test_requires_api_key(self):
        api_user_count = DukeDSUser.api_users.count()
        DukeDSUser.objects.create(dds_id='fewfwef')
        self.assertEqual(api_user_count, DukeDSUser.api_users.count())

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            DukeDSUser.objects.create(dds_id='abcd-1234-fghi-5678', api_key='fwmp2392')


class RelationsTestCase(TestCase):
    pass