from django.db import IntegrityError
from django.test import TestCase
from handover_api.models import DukeDSUser, DukeDSProject, Handover, Share, State, ShareRole


class TransferBaseTestCase(TestCase):

    def setUp(self):
        self.project1 = DukeDSProject.objects.create(project_id='project1')
        self.user1 = DukeDSUser.objects.create(dds_id='user1')
        self.user2 = DukeDSUser.objects.create(dds_id='user2')


class HandoverTestCase(TransferBaseTestCase):
    HANDOVER_EMAIL_TEXT = 'handover email message'
    ACCEPT_EMAIL_TEXT = 'handover accepted'
    REJECT_EMAIL_TEXT = 'handover rejected'

    def setUp(self):
        super(HandoverTestCase, self).setUp()
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


class ShareTestCase(TransferBaseTestCase):

    def setUp(self):
        super(ShareTestCase, self).setUp()
        Share.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_initial_state(self):
        share = Share.objects.first()
        self.assertEqual(share.state, State.NEW, 'New shares should be in initiated state')
        self.assertEqual(share.role, ShareRole.DEFAULT, 'New shares should have default role')

    def test_required_fields(self):
        with self.assertRaises(ValueError):
            Share.objects.create(project=None, from_user=None, to_user=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Share.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)

    def test_allows_multiple_shares(self):
        user3 = DukeDSUser.objects.create(dds_id='user3')
        d = Share.objects.create(project=self.project1, from_user=self.user1, to_user=user3)
        self.assertIsNotNone(d)

    def test_allows_multiple_shares_different_roles(self):
        v = Share.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2, role=ShareRole.VIEW)
        d = Share.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2, role=ShareRole.EDIT)
        self.assertIsNotNone(v)
        self.assertIsNotNone(d)
        self.assertNotEqual(v, d)


class ProjectTestCase(TestCase):
    def test_requires_project_id(self):
        with self.assertRaises(IntegrityError):
            DukeDSProject.objects.create(project_id=None)

    def test_create_project(self):
        p = DukeDSProject.objects.create(project_id='abcd-1234')
        self.assertIsNotNone(p)

    def test_populated(self):
        p = DukeDSProject.objects.create(project_id='abcd-1234')
        self.assertFalse(p.populated())
        p.name = 'A Project'
        self.assertTrue(p.populated())

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

    def test_populated(self):
        u = DukeDSUser.objects.create(dds_id='1234-abcd-fghi-5678')
        self.assertFalse(u.populated())
        u.full_name = 'Test user'
        self.assertFalse(u.populated())
        u.email = 'email@domain.com'
        self.assertTrue(u.populated())


class HandoverRelationsTestCase(TransferBaseTestCase):
    def setUp(self):
        super(HandoverRelationsTestCase, self).setUp()
        self.project2 = DukeDSProject.objects.create(project_id='project2')
        self.project3 = DukeDSProject.objects.create(project_id='project3')
        self.user3 = DukeDSUser.objects.create(dds_id='user3')
        self.h1 = Handover.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2)
        self.h2 = Handover.objects.create(project=self.project2, from_user=self.user1, to_user=self.user3)
        self.h3 = Handover.objects.create(project=self.project3, from_user=self.user2, to_user=self.user3)

    def test_handovers_from(self):
        self.assertIn(self.h1, self.user1.handovers_from.all())
        self.assertIn(self.h2, self.user1.handovers_from.all())
        self.assertNotIn(self.h3, self.user1.handovers_from.all())
        self.assertIn(self.h3, self.user2.handovers_from.all())

    def test_handovers_to(self):
        self.assertIn(self.h1, self.user2.handovers_to.all())
        self.assertIn(self.h2, self.user3.handovers_to.all())
        self.assertIn(self.h3, self.user3.handovers_to.all())
        self.assertNotIn(self.h2, self.user2.handovers_to.all())

    def test_delete_user_deletes_handovers(self):
        initial = Handover.objects.count()
        # Deleting user 3 should delete h1 and h2
        self.user3.delete()
        expected = initial - 2
        self.assertEqual(Handover.objects.count(), expected)

    def test_delete_handovers_keeps_users_and_projects(self):
        users = DukeDSUser.objects.count()
        projects = DukeDSProject.objects.count()
        Handover.objects.all().delete()
        self.assertEqual(DukeDSUser.objects.count(), users)
        self.assertEqual(DukeDSProject.objects.count(), projects)


class ShareRelationsTestCase(TransferBaseTestCase):
    def setUp(self):
        super(ShareRelationsTestCase, self).setUp()
        self.project4 = DukeDSProject.objects.create(project_id='project4')
        self.project5 = DukeDSProject.objects.create(project_id='project5')
        self.user4 = DukeDSUser.objects.create(dds_id='user4')
        self.d1 = Share.objects.create(project=self.project1, from_user=self.user1, to_user=self.user4)
        self.d4 = Share.objects.create(project=self.project4, from_user=self.user2, to_user=self.user4)
        self.d5 = Share.objects.create(project=self.project5, from_user=self.user2, to_user=self.user1)

    def test_shares_from(self):
        self.assertIn(self.d1, self.user1.shares_from.all())
        self.assertIn(self.d4, self.user2.shares_from.all())
        self.assertNotIn(self.d4, self.user1.shares_from.all())
        self.assertIn(self.d5, self.user2.shares_from.all())

    def test_shares_to(self):
        self.assertIn(self.d1, self.user4.shares_to.all())
        self.assertIn(self.d4, self.user4.shares_to.all())
        self.assertIn(self.d5, self.user1.shares_to.all())
        self.assertNotIn(self.d5, self.user4.shares_to.all())

    def test_delete_user_deletes_shares(self):
        initial = Share.objects.count()
        self.user4.delete()
        expected = initial - 2
        self.assertEqual(Share.objects.count(), expected)

    def test_delete_handovers_keeps_users_and_projects(self):
        users = DukeDSUser.objects.count()
        projects = DukeDSProject.objects.count()
        Share.objects.all().delete()
        self.assertEqual(DukeDSUser.objects.count(), users)
        self.assertEqual(DukeDSProject.objects.count(), projects)
