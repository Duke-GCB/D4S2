from django.test import TestCase
from d4s2_api_v2.models import DDSDeliveryPreview


class DDSDeliveryPreviewTestCase(TestCase):

    def setUp(self):
        self.preview = DDSDeliveryPreview(
            from_user_id='from-user-1',
            to_user_id='to-user-2',
            project_id='project-3',
            transfer_id='transfer-4',
            user_message='User Message'
        )

    def test_initialize_object(self):
        self.assertIsNotNone(self.preview)

    def test_defaults_delivery_email_text(self):
        self.assertEqual(self.preview.delivery_email_text, '')

