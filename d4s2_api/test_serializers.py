from django.test import TestCase
from d4s2_api.serializers import DeliverySerializer, SHARE_USERS_INVALID_MSG
from d4s2_api.models import DukeDSProject, DukeDSUser, Delivery


class DeliverySerializerTestCase(TestCase):
    def setUp(self):
        self.data = {
            'project_id': 'project-1234',
            'from_user_id': 'user-5678',
            'to_user_id': 'user-9999',
            'transfer_id': 'abcd-1234-efgh-5678',
        }

    def test_serializes_delivery(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.project.project_id, self.data['project_id'])
        self.assertEqual(delivery.from_user.dds_id, self.data['from_user_id'])
        self.assertEqual(delivery.to_user.dds_id, self.data['to_user_id'])

    def test_serializes_delivery_with_share_user_ids(self):
        mydata = dict(self.data)
        mydata['share_user_ids'] = ['user-1111', 'user-4949']
        serializer = DeliverySerializer(data=mydata)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.project.project_id, self.data['project_id'])
        self.assertEqual(delivery.from_user.dds_id, self.data['from_user_id'])
        self.assertEqual(delivery.to_user.dds_id, self.data['to_user_id'])
        shared_to_user_dds_ids = [user.dds_id for user in delivery.share_to_users.all()]
        self.assertEqual(shared_to_user_dds_ids, ['user-1111', 'user-4949'])

    def test_serializes_delivery_prevents_to_user_in_share_users(self):
        mydata = dict(self.data)
        mydata['share_user_ids'] = [self.data['to_user_id']]
        serializer = DeliverySerializer(data=mydata)
        self.assertFalse(serializer.is_valid())
        self.assertIn(SHARE_USERS_INVALID_MSG, serializer.errors['non_field_errors'])

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
        serializer = DeliverySerializer(delivery, data=data) # Updates the existing instance
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
        serializer = DeliverySerializer(delivery, data=data) # Updates the existing instance
        self.assertTrue(serializer.is_valid(), serializer.errors)

        updated_delivery = serializer.save()
        self.assertEqual(DukeDSProject.objects.count(), 2, "changing id should not create another project")

        # Check for side effects
        expected_original_project = DukeDSProject.objects.get(project_id=original_project_id)
        self.assertEqual(original_project, expected_original_project)
        self.assertNotEqual(original_project, updated_delivery.project)

    def test_valid_without_user_message(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertNotIn('user_message', self.data, 'Data must not have user_message yet')
        self.assertTrue(serializer.is_valid(), 'serializer should be valid even without a user message')
        delivery = serializer.save()
        self.assertIsNone(delivery.user_message)

    def test_valid_with_user_message(self):
        user_message = 'User-submitted message'
        self.data['user_message'] = user_message
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid(), 'serializer should be valid with a user message')
        delivery = serializer.save()
        self.assertEqual(delivery.user_message, user_message)
