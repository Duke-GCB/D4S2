from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from handover_api.views import *
from handover_api.models import *


class HandoverViewTestCase(APITestCase):

    def test_create_handover(self):
        url = reverse('handover-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Handover.objects.count(), 1)
        self.assertEqual(Handover.objects.get().from_user_id, 'user1')

    def test_list_handovers(self):
        Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')
        Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('handover-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_handover(self):
        h = Handover.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_handover(self):
        h = Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Handover.objects.count(), 0)

    def test_update_handover(self):
        h = Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        updated = {'project_id': 'project3', 'from_user_id': 'fromuser1', 'to_user_id':'touser1'}
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Handover.objects.get(pk=h.pk)
        self.assertEqual(h.project_id, 'project3')


class DraftViewTestCase(APITestCase):

    def test_create_draft(self):
        url = reverse('draft-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Draft.objects.count(), 1)
        self.assertEqual(Draft.objects.get().from_user_id, 'user1')

    def test_list_drafts(self):
        Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')
        Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('draft-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_draft(self):
        d =  Draft.objects.create(project_id='project1', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_draft(self):
        d =  Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Draft.objects.count(), 0)

    def test_update_draft(self):
        d =  Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        updated = {'project_id': 'project3', 'from_user_id': 'fromuser1', 'to_user_id':'touser1'}
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d =  Draft.objects.get(pk=d.pk)
        self.assertEqual(d.project_id, 'project3')

class UserViewTestCase(APITestCase):

    def test_create_user(self):
        data = {'dds_id': 'abcd-1234-efgh-5678', 'api_key': 'zxdel8h4g3lvnkqenlf/z'}
        url = reverse('user-list')
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().dds_id, 'abcd-1234-efgh-5678')

    def test_get_users(self):
        User.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        User.objects.create(dds_id='abcd-1234-efgh-5679', api_key='zxdel8h4g3lvnkqenl7')
        url = reverse('user-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_user(self):
        u = User.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('user-detail', args=(u.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dds_id'],'abcd-1234-efgh-5678')

    def test_update_user(self):
        u = User.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('user-detail', args=(u.pk,))
        data = {'dds_id':'abcd-5555-0000-ffff', 'api_key':'zxdel8h4g3lvnkqenlf'}
        response = self.client.put(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        u = User.objects.get(pk=u.pk)
        self.assertEqual(u.dds_id,'abcd-5555-0000-ffff')

    def test_delete_user(self):
        u = User.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('user-detail', args=(u.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.objects.count(), 0)


