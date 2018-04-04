"""
Tests migrations that move DukeDS uuids around.
TestMigrations from https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
"""
from django.apps import apps
from django.test import TransactionTestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection


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
            to_user=DukeDSUser.objects.create(dds_id='qr-789')
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
