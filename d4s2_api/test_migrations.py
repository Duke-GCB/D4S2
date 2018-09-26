"""
Tests migrations that move DukeDS uuids around.
TestMigrations from https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
"""
from django.apps import apps
from django.test import TransactionTestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.contrib.auth.models import Group, User
from django.core.management import call_command


class TestMigrations(TransactionTestCase):
    """
    Modifies setUp to migrate to the migration name in `migrate_from` then run `setUpBeforeMigration(apps)`
    finally finishes migrating to `migrate_to`. Use app apps.get_model to create model objects.
    """
    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None
    django_application = None

    def setUp(self):
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass

    def tearDown(self):
        # Leave the db in the final state so that the test runner doesn't
        # error when truncating the database.
        # https://micknelson.wordpress.com/2013/03/01/testing-django-migrations/
        call_command('migrate', self.django_application, verbosity=0)


class DukeDSIDMigrationTestCase(TestMigrations):
    """
    Runs migrations to the point where Delivery/Share had references to DukeDSProject/DukeDSUser
    Sets up some sample data. Finishes migrations to where we store the UUIDs instead and runs tests to make sure
    the data has successfully migrated.
    """
    migrate_from = '0007_delivery_share_to_users'
    migrate_to = '0013_1_dds_id_fields_not_null'

    def setUpBeforeMigration(self, apps):
        Delivery = apps.get_model('d4s2_api', 'Delivery')
        DukeDSProject = apps.get_model('d4s2_api', 'DukeDSProject')
        DukeDSUser = apps.get_model('d4s2_api', 'DukeDSUser')
        project = DukeDSProject.objects.create()

        delivery = Delivery.objects.create(
            project=DukeDSProject.objects.create(project_id='ab-123'),
            from_user=DukeDSUser.objects.create(dds_id='cd-456'),
            to_user=DukeDSUser.objects.create(dds_id='ef-789')
        )
        delivery.share_to_users = [
            DukeDSUser.objects.create(dds_id='gh-111'),
            DukeDSUser.objects.create(dds_id='ij-222'),
            DukeDSUser.objects.create(dds_id='kl-333'),
        ]
        delivery.save()

        Share = apps.get_model('d4s2_api', 'Share')
        Share.objects.create(
            project=DukeDSProject.objects.create(project_id='mn-123'),
            from_user=DukeDSUser.objects.create(dds_id='op-456'),
            to_user=DukeDSUser.objects.create(dds_id='qr-789'),
        )

    def test_delivery_ids_migrated(self):
        Delivery = apps.get_model('d4s2_api', 'Delivery')

        deliveries = Delivery.objects.all()
        self.assertEqual(len(deliveries), 1)
        delivery = deliveries[0]
        self.assertEqual(delivery.project_id, 'ab-123')
        self.assertEqual(delivery.from_user_id, 'cd-456')
        self.assertEqual(delivery.to_user_id, 'ef-789')

        share_users = delivery.shared_to_users.all()
        self.assertEqual(set(['gh-111', 'ij-222', 'kl-333']), set([user.dds_id for user in share_users]))

    def test_delivery_ids_migrated(self):
        Share = apps.get_model('d4s2_api', 'Share')

        shares = Share.objects.all()
        self.assertEqual(len(shares), 1)
        share = shares[0]
        self.assertEqual(share.project_id, 'mn-123')
        self.assertEqual(share.from_user_id, 'op-456')
        self.assertEqual(share.to_user_id, 'qr-789')

    def tearDown(self):
        # Delete deliveries since the migration that when email_template_set is required
        # TestMigrations.tearDown() will not fail in
        Delivery = self.apps.get_model('d4s2_api', 'Delivery')
        Delivery.objects.all().delete()
        super(DukeDSIDMigrationTestCase, self).tearDown()


class EmailTemplateGroupMigrationTestCase(TestMigrations):
    """
    Runs migrations to the point where EmailTemplate has both group and template_set fields.
    Sets up some sample EmailTemplates that have group filled in.
    Finishes migrations to where only template_set remains.
    """
    migrate_from = '0015_auto_20180323_1757'
    migrate_to = '0017_auto_20180323_1833'

    def setUpBeforeMigration(self, apps):
        EmailTemplate = apps.get_model('d4s2_api', 'EmailTemplate')
        EmailTemplateType = apps.get_model('d4s2_api', 'EmailTemplateType')

        user1 = User.objects.create_user('user1')
        group1 = Group.objects.create(name='group1')
        group1.user_set.add(user1)

        user2 = User.objects.create_user('user2')
        group2 = Group.objects.create(name='group2')
        group2.user_set.add(user2)

        delivery_type = EmailTemplateType.objects.create(name='delivery')
        share_project_viewer_type = EmailTemplateType.objects.create(name='share_project_viewer')

        # NOTE: Had to assign group and owner by id any other method failed with error message like:
        # Cannot assign "<Group: group1>": "EmailTemplate.group" must be a "Group" instance.
        EmailTemplate.objects.create(
            group_id=group1.id,
            owner_id=user1.id,
            template_type=delivery_type,
            body='some text',
            subject='title1',
        )
        EmailTemplate.objects.create(
            group_id=group1.id,
            owner_id=user1.id,
            template_type=share_project_viewer_type,
            body='some text',
            subject='title2',
        )
        EmailTemplate.objects.create(
            group_id=group2.id,
            owner_id=user2.id,
            template_type=delivery_type,
            body='some text',
            subject='title3',
        )

    def test_delivery_ids_migrated(self):
        """
        The group field should migrated to the template_set.
        Testing migration 0016_email_group_to_set.
        """
        EmailTemplate = apps.get_model('d4s2_api', 'EmailTemplate')
        email_templates = EmailTemplate.objects.all()
        self.assertEqual(len(email_templates), 3)
        template_info = [(email_template.subject, email_template.template_set.name)
                         for email_template in email_templates]
        self.assertEqual({
            ('title1', 'group1'),
            ('title2', 'group1'),
            ('title3', 'group2'),
        }, set(template_info))

    def test_user_email_template_sets_migrated(self):
        UserEmailTemplateSet = apps.get_model('d4s2_api', 'UserEmailTemplateSet')
        user_email_template_sets = UserEmailTemplateSet.objects.all()
        user_email_template_sets_info = [
            (user_email_template_set.user.username, user_email_template_set.email_template_set.name)
            for user_email_template_set in user_email_template_sets
        ]
        self.assertEqual(set(user_email_template_sets_info),
                         {('user1', u'group1'), ('user2', u'group2')})


class EmailTemplateServiceNameTest(TestMigrations):
    """
    Tests that the string 'Duke Data Service' in email templates is updated to {{ service_name }}
    """

    migrate_from = '0024_auto_20180423_2026'
    migrate_to = '0025_auto_20180430_1549'

    def setUpBeforeMigration(self, apps):
        EmailTemplate = apps.get_model('d4s2_api', 'EmailTemplate')
        EmailTemplateType = apps.get_model('d4s2_api', 'EmailTemplateType')
        EmailTemplateSet = apps.get_model('d4s2_api', 'EmailTemplateSet')

        user1 = User.objects.create_user('user1')
        type1 = EmailTemplateType.objects.create(name='template_type1')
        set1 = EmailTemplateSet.objects.create(name='template_set1')

        EmailTemplate.objects.create(
            template_set=set1,
            owner_id=user1.id,
            template_type=type1,
            body='Your data in Duke Data Service is ready at {{ accept_url }}.\\r\\nPlease visit Duke Data Service.',
            subject='Data from Duke Data Service sent by {{ sender_name }}',
        )

    def test_name_replaced(self):
        EmailTemplate = apps.get_model('d4s2_api', 'EmailTemplate')
        template = EmailTemplate.objects.first()
        self.assertEqual(template.body, 'Your data in {{ service_name }} is ready at {{ accept_url }}.\\r\\nPlease visit {{ service_name }}.')
        self.assertEqual(template.subject, 'Data from {{ service_name }} sent by {{ sender_name }}')
