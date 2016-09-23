from django.test import TestCase
from d4s2_api.serializers import DeliverySerializer
from d4s2_api.models import DukeDSProject, DukeDSUser, Delivery


class DeliverySerializerTestCase(TestCase):
    def setUp(self):
        self.data = {
            'project_id': 'project-1234',
            'from_user_id': 'user-5678',
            'to_user_id': 'user-9999',
        }

    def test_serializes_delivery(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.project.project_id, self.data['project_id'])
        self.assertEqual(delivery.from_user.dds_id, self.data['from_user_id'])
        self.assertEqual(delivery.to_user.dds_id, self.data['to_user_id'])

    def test_finds_related_project(self):
        p = DukeDSProject.objects.create(project_id=self.data['project_id'])
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.project, p)

    def test_finds_related_users(self):
        from_user = DukeDSUser.objects.create(dds_id=self.data['from_user_id'])
        to_user = DukeDSUser.objects.create(dds_id=self.data['to_user_id'])
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.from_user, from_user)
        self.assertEqual(delivery.to_user, to_user)

    def test_changing_project_id_creates_new(self):
        # Create an initial delivery, project, and users
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        original_delivery_pk = delivery.pk
        self.assertIsNotNone(delivery)
        original_project = delivery.project
        original_project_id = delivery.project.project_id

        self.assertEqual(DukeDSProject.objects.count(), 1, "should have one project")

        # Update the serialized instance and change the project id
        data = dict(self.data)
        data['project_id'] = 'project0000'
        serializer = DeliverySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        updated_delivery = serializer.save()
        self.assertEqual(DukeDSProject.objects.count(), 2, "changing id should create another project")

        # Check for side effects
        expected_original_project = DukeDSProject.objects.get(project_id=original_project_id)
        self.assertEqual(original_project, expected_original_project)
        self.assertNotEqual(original_project, updated_delivery.project)

    def test_changing_project_id_matches_other(self):
        # Create an initial delivery, project, and users
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        original_delivery_pk = delivery.pk
        self.assertIsNotNone(delivery)
        original_project = delivery.project
        original_project_id = delivery.project.project_id

        self.assertEqual(DukeDSProject.objects.count(), 1, "should have one project")

        # Now create a second project
        project0000 = DukeDSProject.objects.create(project_id='project0000')
        self.assertEqual(DukeDSProject.objects.count(), 2)

        # Update the serialized instance and change the project id
        data = dict(self.data)
        data['project_id'] = project0000.project_id
        serializer = DeliverySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        updated_delivery = serializer.save()
        self.assertEqual(DukeDSProject.objects.count(), 2, "changing id should not create another project")

        # Check for side effects
        expected_original_project = DukeDSProject.objects.get(project_id=original_project_id)
        self.assertEqual(original_project, expected_original_project)
        self.assertNotEqual(original_project, updated_delivery.project)