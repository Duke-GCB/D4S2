from django.test import TestCase
from d4s2_api_v2.serializers import DDSDeliveryPreviewSerializer, UserSerializer
from django.contrib.auth.models import User as django_user
from mock import patch, call


class DeliveryPreviewSerializerTestCase(TestCase):
    def setUp(self):
        self.data = {
            'project_id': 'project-1234',
            'from_user_id': 'user-5678',
            'to_user_id': 'user-9999',
            'user_message': '',
            'transfer_id': ''
        }

    def test_validates(self):
        serializer = DDSDeliveryPreviewSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())

    def test_ignores_delivery_email_text(self):
        self.data['delivery_email_text'] = 'Hello world'
        serializer = DDSDeliveryPreviewSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertNotIn('delivery_email_text', serializer.validated_data)

    def test_invalid_without_user_message_field(self):
        del self.data['user_message']
        self.assertNotIn('user_message', self.data)
        serializer = DDSDeliveryPreviewSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())

    def test_invalid_without_transfer_id_field(self):
        del self.data['transfer_id']
        self.assertNotIn('transfer_id', self.data)
        serializer = DDSDeliveryPreviewSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())


class UserSerializerSerializerTestCase(TestCase):
    @patch('d4s2_api_v2.serializers.UserEmailTemplateSet')
    def test_create(self, mock_user_email_template_set):
        mock_user_email_template_set.user_is_setup.return_value = True
        user = django_user.objects.create_user(username='user', password='secret')
        serializer = UserSerializer(user)
        self.assertEqual(serializer.data['username'], user.username)
        self.assertEqual(serializer.data['setup_for_delivery'], True)
        self.assertEqual(serializer.data['setup_for_cloud_delivery'], True)
        mock_user_email_template_set.user_is_setup.assert_has_calls([
            call(user, 'dds'),
            call(user, 'azure'),
        ])
