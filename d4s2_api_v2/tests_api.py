from django.core.urlresolvers import reverse
from rest_framework import status
from django.contrib.auth.models import User as django_user
from rest_framework.test import APITestCase
from gcb_web_auth.tests_dukeds_auth import ResponseStatusCodeTestCase
from d4s2_api_v2.models import *

class AuthenticatedResourceTestCase(APITestCase, ResponseStatusCodeTestCase):
    def setUp(self):
        username = 'api_user'
        password = 'secret'
        self.user = django_user.objects.create_user(username, password=password, is_staff=True)
        self.client.login(username=username, password=password)
        self.ddsuser1 = DukeDSUser.objects.create(user=self.user, dds_id='user1')
        self.ddsuser2 = DukeDSUser.objects.create(dds_id='user2')
        self.ddsuser3 = DukeDSUser.objects.create(dds_id='user3')
        self.project1 = DukeDSProject.objects.create(project_id='project1', name='Project 1')
        self.project2 = DukeDSProject.objects.create(project_id='project2', name='Project 2')
        self.project3 = DukeDSProject.objects.create(project_id='project3', name='Project 3')
        self.transfer_id1 = 'abcd-1234'
        self.transfer_id2 = 'efgh-5678'
        self.transfer_id3 = 'ijkl-9012'

    def assertNotAllowed(self, response):
        # TODO: Move to ResponseStatusCodeTestCase
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED,
                         'Got {}, expected 405 when method is not allowed'
                         .format(response.status_code))


class DeliveryAPITestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('delivery-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_is_readonly(self):
        d = Delivery.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                    transfer_id=self.transfer_id1)
        list_url = reverse('delivery-list')
        response = self.client.post(list_url , {}, format='json')
        self.assertNotAllowed(response)

        detail_url = reverse('delivery-detail', args=(d.pk,))
        response = self.client.delete(detail_url, format='json')
        self.assertNotAllowed(response)

        response = self.client.put(detail_url, {}, format='json')
        self.assertNotAllowed(response)

    def test_lists_users_deliveries(self):
        Delivery.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                transfer_id=self.transfer_id1)
        Delivery.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                transfer_id=self.transfer_id2)
        url = reverse('delivery-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_gets_single_delivery(self):
        d = Delivery.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                    transfer_id=self.transfer_id1)
        Delivery.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                transfer_id=self.transfer_id2)
        detail_url = reverse('delivery-detail', args=(d.pk,))
        response = self.client.get(detail_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('id'), d.pk)

    def test_lists_only_deliveries_sent_by_user(self):
        sent = Delivery.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                           transfer_id=self.transfer_id1)
        received = Delivery.objects.create(project=self.project2, from_user=self.ddsuser2, to_user=self.ddsuser1,
                                             transfer_id=self.transfer_id2)
        unrelated = Delivery.objects.create(project=self.project3, from_user=self.ddsuser2, to_user=self.ddsuser3,
                                             transfer_id=self.transfer_id3)
        url = reverse('delivery-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        delivery_ids = [d['id'] for d in response.data]
        self.assertIn(sent.pk, delivery_ids)
        self.assertNotIn(received.pk, delivery_ids)
        self.assertNotIn(unrelated.pk, delivery_ids)


class DukeDSUserAPITestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('dukedsuser-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_api_is_readonly(self):
        d = DukeDSUser.objects.create(dds_id='test-user')
        list_url = reverse('dukedsuser-list')
        response = self.client.post(list_url , {}, format='json')
        self.assertNotAllowed(response)

        detail_url = reverse('dukedsuser-detail', args=(d.pk,))
        response = self.client.delete(detail_url, format='json')
        self.assertNotAllowed(response)

        response = self.client.put(detail_url, {}, format='json')
        self.assertNotAllowed(response)

    def test_lists_all_users(self):
        model_ids = [u.pk for u in DukeDSUser.objects.all()]
        self.assertGreater(len(model_ids), 0)
        url = reverse('dukedsuser-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(model_ids))
        api_ids = [u['id'] for u in response.data]
        self.assertEqual(api_ids, model_ids)


class DukeDSProjectAPITestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('dukedsproject-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_api_is_readonly(self):
        p = DukeDSProject.objects.create(project_id='test-project', name='Test Project')
        list_url = reverse('dukedsproject-list')
        response = self.client.post(list_url , {}, format='json')
        self.assertNotAllowed(response)

        detail_url = reverse('dukedsproject-detail', args=(p.pk,))
        response = self.client.delete(detail_url, format='json')
        self.assertNotAllowed(response)

        response = self.client.put(detail_url, {}, format='json')
        self.assertNotAllowed(response)

    def test_lists_only_projects_user_is_delivering(self):
        delivering = DukeDSProject.objects.create(project_id='delivering-project')
        receiving = DukeDSProject.objects.create(project_id='receiving-project')
        unrelated = DukeDSProject.objects.create(project_id='unrelated-project')

        Delivery.objects.create(project=delivering, from_user=self.ddsuser1, to_user=self.ddsuser2,
                                transfer_id=self.transfer_id1)
        Delivery.objects.create(project=receiving, from_user=self.ddsuser2, to_user=self.ddsuser1,
                                transfer_id=self.transfer_id2)
        Delivery.objects.create(project=unrelated, from_user=self.ddsuser2, to_user=self.ddsuser3,
                                transfer_id=self.transfer_id3)

        list_url = reverse('dukedsproject-list')
        response = self.client.get(list_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ids = [p['id'] for p in response.data]
        self.assertIn(delivering.pk, response_ids)
        self.assertNotIn(receiving.pk, response_ids)
        self.assertNotIn(unrelated.pk, response_ids)
