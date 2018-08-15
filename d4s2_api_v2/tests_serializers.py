from django.test import TestCase
from d4s2_api_v2.models import DDSDeliveryPreview
from d4s2_api_v2.serializers import DDSDeliveryPreviewSerializer
from mock import MagicMock


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
