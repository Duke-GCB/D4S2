from django.test import TestCase
from d4s2_api_v2.serializers import *
from d4s2_api_v2.models import *

class SerializerTestCase(TestCase):

    def setUp(self):
        self.project1 = DukeDSProject.objects.create(project_id='project1', name='Project 1')
        self.ddsuser1 = DukeDSUser.objects.create(dds_id='user1', full_name='User One', email='user@host.com')
        self.ddsuser2 = DukeDSUser.objects.create(dds_id='user2')
        self.ddsuser3 = DukeDSUser.objects.create(dds_id='user3')
        self.ddsuser4 = DukeDSUser.objects.create(dds_id='user4')
        self.transferid1 = 'transfer-1'
        self.delivery1 = Delivery.objects.create(project=self.project1,
                                                 from_user=self.ddsuser1,
                                                 to_user=self.ddsuser2,
                                                 transfer_id=self.transferid1)
        self.delivery1.share_to_users = [self.ddsuser3, self.ddsuser4]
        self.delivery1.save()


class DeliverySerializerTestCase(SerializerTestCase):

    def test_serializes_delivery_model(self):
        serialized = DeliverySerializer(self.delivery1).data
        self.assertEqual(serialized['id'], self.delivery1.pk)
        self.assertEqual(serialized['project'], self.project1.pk)
        self.assertEqual(serialized['from_user'], self.ddsuser1.pk)
        self.assertEqual(serialized['to_user'], self.ddsuser2.pk)
        self.assertEqual(serialized['transfer_id'], self.transferid1)
        self.assertEqual(serialized['share_to_users'], [3, 4])


class DukeDSUserSerializerTestCase(SerializerTestCase):

    def test_serializes_dukedsuser_model(self):
        serialized = DukeDSUserSerializer(self.ddsuser1).data
        self.assertEqual(serialized['id'], self.ddsuser1.pk)
        self.assertEqual(serialized['dds_id'], self.ddsuser1.dds_id)
        self.assertEqual(serialized['full_name'], self.ddsuser1.full_name)
        self.assertEqual(serialized['email'], self.ddsuser1.email)

class DukeDSProjectSerializerTestCase(SerializerTestCase):

    def test_serializes_dukedsproject_model(self):
        serialized = DukeDSProjectSerializer(self.project1).data
        self.assertEqual(serialized['id'], self.project1.pk)
        self.assertEqual(serialized['project_id'], self.project1.project_id)
        self.assertEqual(serialized['name'], self.project1.name)
