from django.db import IntegrityError
from django.test import TestCase
from d4s2_api.models import *
from django.contrib.auth.models import User, Group

class TransferBaseTestCase(TestCase):

    def setUp(self):
        self.project1 = DukeDSProject.objects.create(project_id='project1')
        self.user1 = DukeDSUser.objects.create(dds_id='user1')
        self.user2 = DukeDSUser.objects.create(dds_id='user2')
        self.transfer_id = 'abcd-1234-efgh-6789'


class DeliveryTestCase(TransferBaseTestCase):
    DELIVERY_EMAIL_TEXT = 'delivery email message'
    ACCEPT_EMAIL_TEXT = 'delivery accepted'
    DECLINE_EMAIL_TEXT = 'delivery declined'

    def setUp(self):
        super(DeliveryTestCase, self).setUp()
        Delivery.objects.create(project=self.project1,
                                from_user=self.user1,
                                to_user=self.user2,
                                transfer_id=self.transfer_id)

    def test_initial_state(self):
        delivery = Delivery.objects.first()
        self.assertEqual(delivery.state, State.NEW, 'New deliveries should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(ValueError):
            Delivery.objects.create(project=None, from_user=None, to_user=None, transfer_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Delivery.objects.create(project=self.project1,
                                    from_user=self.user1,
                                    to_user=self.user2,
                                    transfer_id=self.transfer_id)

    def test_mark_notified(self):
        delivery = Delivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_notified(DeliveryTestCase.DELIVERY_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.NOTIFIED)

    def test_mark_accepted(self):
        performed_by = 'performer'
        delivery = Delivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_accepted(performed_by, DeliveryTestCase.ACCEPT_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.ACCEPTED)
        self.assertEqual(delivery.performed_by, performed_by)
        self.assertEqual(delivery.completion_email_text, DeliveryTestCase.ACCEPT_EMAIL_TEXT)

    def test_mark_declined(self):
        performed_by = 'performer'
        delivery = Delivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_declined(performed_by, 'Wrong person.',  DeliveryTestCase.DECLINE_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Wrong person.')
        self.assertEqual(delivery.performed_by, performed_by)
        self.assertEqual(delivery.completion_email_text, DeliveryTestCase.DECLINE_EMAIL_TEXT)

    def test_is_complete(self):
        delivery = Delivery.objects.first()
        self.assertEqual(delivery.is_complete(), False)
        delivery.mark_notified('')
        self.assertEqual(delivery.is_complete(), False)
        delivery.mark_accepted('','')
        self.assertEqual(delivery.is_complete(), True)
        delivery.mark_declined('','','')
        self.assertEqual(delivery.is_complete(), True)
        delivery.state = State.FAILED
        delivery.save()
        self.assertEqual(delivery.is_complete(), True)

    def setup_incomplete_delivery(self):
        delivery = Delivery.objects.first()
        delivery.transfer_id = self.transfer_id
        delivery.save()
        self.assertFalse(delivery.is_complete())
        return delivery

    def test_updates_local_state_accepted(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'accepted'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.ACCEPTED)
        self.assertEqual(delivery.decline_reason, '')

    def test_updates_local_state_rejected(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'rejected', 'status_comment': 'Bad Data'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Bad Data')

    def test_updates_local_state_pending(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'pending'})
        self.assertFalse(delivery.is_complete())
        self.assertEqual(delivery.state, State.NEW)
        self.assertEqual(delivery.decline_reason, '')

    def test_update_without_changes(self):
        delivery = self.setup_incomplete_delivery()
        delivery.mark_declined('jsmith','Bad Data', DeliveryTestCase.DECLINE_EMAIL_TEXT)
        self.assertTrue(delivery.is_complete())
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'rejected', 'status_comment': 'Changed Comment'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Bad Data', 'Should not change when status doesnt change')

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
        DukeDSUser.objects.create(dds_id='abcd-1234-fghi-5678')

    def test_required_fields_dds_id(self):
        with self.assertRaises(IntegrityError):
            DukeDSUser.objects.create(dds_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            DukeDSUser.objects.create(dds_id='abcd-1234-fghi-5678')

    def test_populated(self):
        u = DukeDSUser.objects.create(dds_id='1234-abcd-fghi-5678')
        self.assertFalse(u.populated())
        u.full_name = 'Test user'
        self.assertFalse(u.populated())
        u.email = 'email@domain.com'
        self.assertTrue(u.populated())


class DeliveryRelationsTestCase(TransferBaseTestCase):
    def setUp(self):
        super(DeliveryRelationsTestCase, self).setUp()
        self.project2 = DukeDSProject.objects.create(project_id='project2')
        self.project3 = DukeDSProject.objects.create(project_id='project3')
        self.user3 = DukeDSUser.objects.create(dds_id='user3')
        self.h1 = Delivery.objects.create(project=self.project1, from_user=self.user1, to_user=self.user2, transfer_id='1')
        self.h2 = Delivery.objects.create(project=self.project2, from_user=self.user1, to_user=self.user3, transfer_id='2')
        self.h3 = Delivery.objects.create(project=self.project3, from_user=self.user2, to_user=self.user3, transfer_id='3')

    def test_deliveries_from(self):
        self.assertIn(self.h1, self.user1.deliveries_from.all())
        self.assertIn(self.h2, self.user1.deliveries_from.all())
        self.assertNotIn(self.h3, self.user1.deliveries_from.all())
        self.assertIn(self.h3, self.user2.deliveries_from.all())

    def test_deliveries_to(self):
        self.assertIn(self.h1, self.user2.deliveries_to.all())
        self.assertIn(self.h2, self.user3.deliveries_to.all())
        self.assertIn(self.h3, self.user3.deliveries_to.all())
        self.assertNotIn(self.h2, self.user2.deliveries_to.all())

    def test_delete_user_deletes_deliveries(self):
        initial = Delivery.objects.count()
        # Deleting user 3 should delete h1 and h2
        self.user3.delete()
        expected = initial - 2
        self.assertEqual(Delivery.objects.count(), expected)

    def test_delete_deliveries_keeps_users_and_projects(self):
        users = DukeDSUser.objects.count()
        projects = DukeDSProject.objects.count()
        Delivery.objects.all().delete()
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

    def test_delete_deliveries_keeps_users_and_projects(self):
        users = DukeDSUser.objects.count()
        projects = DukeDSProject.objects.count()
        Share.objects.all().delete()
        self.assertEqual(DukeDSUser.objects.count(), users)
        self.assertEqual(DukeDSProject.objects.count(), projects)


class EmailTemplateTypeTestCase(TestCase):

    def requires_unique_types(self):
        EmailTemplateType.objects.create(name='type1')
        with self.assertRaises(IntegrityError):
            EmailTemplateType.objects.create(name='type1')

    def test_initial_data(self):
        """
        Data for this is loaded by a migration, make sure it's there.
        :return:
        """
        for role in ShareRole.ROLES:
            self.assertIsNotNone(EmailTemplateType.objects.get(name='share_{}'.format(role)))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='delivery'))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='accepted'))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='declined'))

    def test_from_share_role(self):
        role = 'project_viewer'
        e = EmailTemplateType.from_share_role(role)
        self.assertEqual(e.name, 'share_project_viewer')


class EmailTemplateTestCase(TestCase):

    def setUp(self):
        # email templates depend on groups and users
        self.group = Group.objects.create(name='test_group')
        self.user = User.objects.create(username='test_user')
        self.group.user_set.add(self.user)
        self.dds_project = DukeDSProject.objects.create(project_id='project1')
        self.dds_user1 = DukeDSUser.objects.create(dds_id='user1', user=self.user)
        self.dds_user2 = DukeDSUser.objects.create(dds_id='user2')
        self.default_type = EmailTemplateType.from_share_role(ShareRole.DEFAULT)
        self.download_type = EmailTemplateType.from_share_role(ShareRole.DOWNLOAD)
        self.view_type = EmailTemplateType.from_share_role(ShareRole.VIEW)
        self.transfer_id = 'abc-123'

    def test_create_email_template(self):
        template = EmailTemplate.objects.create(group=self.group,
                                                owner=self.user,
                                                template_type=self.default_type,
                                                subject='Subject',
                                                body='email body')
        self.assertIsNotNone(template)

    def test_prevent_duplicate_types(self):
        template1 = EmailTemplate.objects.create(group=self.group,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        self.assertIsNotNone(template1)
        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(group=self.group,
                                         owner=self.user,
                                         template_type=self.download_type,
                                         subject='Subject',
                                         body='email body 2')

    def test_allows_duplicate_types_outspide_group(self):
        group2 = Group.objects.create(name='group2')
        template1 = EmailTemplate.objects.create(group=self.group,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        self.assertIsNotNone(template1)
        template2 = EmailTemplate.objects.create(group=group2,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        # assert different items but otherwise data is the same
        self.assertIsNotNone(template2)
        self.assertNotEqual(template1, template2)
        self.assertEqual(template1.owner, template2.owner)
        self.assertEqual(template1.subject, template2.subject)
        self.assertEqual(template1.body, template2.body)
        self.assertEqual(template1.template_type, template2.template_type)
        self.assertNotEqual(template1.group, template2.group)

    def test_for_share(self):
        # Create an email template
        EmailTemplate.objects.create(group=self.group,
                                     owner=self.user,
                                     template_type=self.download_type,
                                     subject='Subject',
                                     body='email body')
        share = Share.objects.create(project=self.dds_project,
                                     from_user=self.dds_user1,
                                     to_user=self.dds_user2,
                                     role=ShareRole.DOWNLOAD)
        t = EmailTemplate.for_share(share)
        self.assertIsNotNone(t)
        self.assertEqual(t.body, 'email body')

    def test_for_operation(self):
        # Create an email template
        delivery = Delivery.objects.create(project=self.dds_project,
                                           from_user=self.dds_user1,
                                           to_user=self.dds_user2,
                                           transfer_id=self.transfer_id)
        EmailTemplate.objects.create(group=self.group,
                                     owner=self.user,
                                     template_type=EmailTemplateType.objects.get(name='accepted'),
                                     subject='Acceptance Email Subject',
                                     body='Acceptance Email Body')
        t = EmailTemplate.for_operation(delivery, 'accepted')
        self.assertIsNotNone(t)
        self.assertEqual(t.subject, 'Acceptance Email Subject')

    def test_no_templates(self):
        share = Share.objects.create(project=self.dds_project,
                                     from_user=self.dds_user1,
                                     to_user=self.dds_user2,
                                     role=ShareRole.DOWNLOAD)
        self.assertIsNone(EmailTemplate.for_share(share))

    def test_user_not_found(self):
        # dds_user2 is not bound to a django user, so we can't find templates
        share = Share.objects.create(project=self.dds_project,
                                     from_user=self.dds_user2,
                                     to_user=self.dds_user1,
                                     role=ShareRole.DOWNLOAD)
        with self.assertRaises(EmailTemplateException):
            EmailTemplate.for_share(share)

    def test_multiple_template_error(self):
        # If user is in multiple groups and each has a template for a given role
        # we can't use the simple for_share lookup
        group2 = Group.objects.create(name='group2')
        group2.user_set.add(self.user)
        t1 = EmailTemplate.objects.create(group=self.group,
                                          owner=self.user,
                                          template_type=self.download_type,
                                          subject='Subject',
                                          body='email body')
        t2 = EmailTemplate.objects.create(group=group2,
                                          owner=self.user,
                                          template_type=self.download_type,
                                          subject='Subject',
                                          body='email body')
        self.assertEqual(t1.template_type, t2.template_type)
        self.assertEqual(t1.owner, t2.owner)
        self.assertNotEqual(t1.group, t2.group)
        share = Share.objects.create(project=self.dds_project,
                                     from_user=self.dds_user1,
                                     to_user=self.dds_user2,
                                     role=ShareRole.DOWNLOAD)
        with self.assertRaises(EmailTemplateException):
            EmailTemplate.for_share(share)
