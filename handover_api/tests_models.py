from django.db import IntegrityError
from django.test import TestCase
from handover_api.models import DukeDSUser, Handover, Draft, State


class HandoverTestCase(TestCase):
    HANDOVER_EMAIL_TEXT = 'handover email message'
    ACCEPT_EMAIL_TEXT = 'handover accepted'
    REJECT_EMAIL_TEXT = 'handover rejected'

    def setUp(self):
        Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')

    def test_initial_state(self):
        handover = Handover.objects.first()
        self.assertEqual(handover.state, State.NEW, 'New handovers should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(IntegrityError):
            Handover.objects.create(project_id=None, from_user_id=None, to_user_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')

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
        Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')

    def test_initial_state(self):
        draft = Draft.objects.first()
        self.assertEqual(draft.state, State.NEW, 'New drafts should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(IntegrityError):
            Draft.objects.create(project_id=None, from_user_id=None, to_user_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')


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

