from django.test import TestCase
from d4s2_api.serializers import DeliverySerializer, SHARE_USERS_INVALID_MSG


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
        self.assertEqual(delivery.project_id, self.data['project_id'])
        self.assertEqual(delivery.from_user_id, self.data['from_user_id'])
        self.assertEqual(delivery.to_user_id, self.data['to_user_id'])

    def test_serializes_delivery_with_share_user_ids(self):
        mydata = dict(self.data)
        mydata['share_user_ids'] = ['user-1111', 'user-4949']

        serializer = DeliverySerializer(data=mydata)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        delivery = serializer.save()
        self.assertEqual(delivery.project_id, self.data['project_id'])
        self.assertEqual(delivery.from_user_id, self.data['from_user_id'])
        self.assertEqual(delivery.to_user_id, self.data['to_user_id'])
        shared_to_user_dds_ids = [user.dds_id for user in delivery.share_user_ids.all()]
        self.assertEqual(shared_to_user_dds_ids, ['user-1111', 'user-4949'])

    def test_serializes_delivery_prevents_to_user_in_share_users(self):
        mydata = dict(self.data)
        mydata['share_user_ids'] = [self.data['to_user_id']]
        serializer = DeliverySerializer(data=mydata)
        self.assertFalse(serializer.is_valid())
        self.assertIn(SHARE_USERS_INVALID_MSG, serializer.errors['non_field_errors'])

    def test_finds_related_project(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.project_id, 'project-1234')

    def test_finds_related_users(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        delivery = serializer.save()
        self.assertEqual(delivery.from_user_id, 'user-5678')
        self.assertEqual(delivery.to_user_id, 'user-9999')

    def test_valid_without_user_message(self):
        serializer = DeliverySerializer(data=self.data)
        self.assertNotIn('user_message', self.data, 'Data must not have user_message yet')
        self.assertTrue(serializer.is_valid(raise_exception=True), 'serializer should be valid even without a user message')
        delivery = serializer.save()
        self.assertIsNone(delivery.user_message)

    def test_valid_with_user_message(self):
        user_message = 'User-submitted message'
        self.data['user_message'] = user_message
        serializer = DeliverySerializer(data=self.data)
        self.assertTrue(serializer.is_valid(raise_exception=True), 'serializer should be valid with a user message')
        delivery = serializer.save()
        self.assertEqual(delivery.user_message, user_message)
