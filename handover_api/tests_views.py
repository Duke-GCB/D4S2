from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from mock import patch
from handover_api.views import *
from handover_api.models import *
from django.contrib.auth.models import User as django_user


class AuthenticatedResourceTestCase(APITestCase):
    def setUp(self):
        username = 'api_user'
        password = 'secret'
        self.user = django_user.objects.create_user(username, password=password, is_staff=True)
        self.client.login(username=username, password=password)


class HandoverViewTestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('handover-list')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fails_not_staff(self):
        self.user.is_staff = False
        self.user.save()
        url = reverse('handover-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_filter_handovers(self):
        Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('handover-list')
        response=self.client.get(url, {'project_id': 'project2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    @patch('handover_api.views.send_handover')
    def test_send_handover(self, mock_send_handover):
        h = Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        self.assertTrue(h.is_new())
        url = reverse('handover-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Handover.objects.get(pk=h.pk)
        self.assertFalse(h.is_new())
        self.assertTrue(mock_send_handover.called)

    @patch('handover_api.views.send_handover')
    def test_send_handover_fails(self, mock_send_handover):
        h = Handover.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        self.assertTrue(h.is_new())
        h.mark_notified()
        url = reverse('handover-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_send_handover.called)


class DraftViewTestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('draft-list')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fails_not_staff(self):
        self.user.is_staff = False
        self.user.save()
        url = reverse('draft-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

    @patch('handover_api.views.send_draft')
    def test_send_draft(self, mock_draft):
        d =  Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        self.assertFalse(d.is_notified())
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Draft.objects.get(pk=d.pk)
        self.assertTrue(d.is_notified())
        self.assertTrue(mock_draft.called)

    @patch('handover_api.views.send_draft')
    def test_send_draft_fails(self, mock_draft):
        d =  Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        self.assertFalse(d.is_notified())
        d.mark_notified()
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_draft.called)

    @patch('handover_api.views.send_draft')
    def test_force_send_draft(self, mock_draft):
        d =  Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        self.assertFalse(d.is_notified())
        d.mark_notified()
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_draft.called)

    def test_filter_drafts(self):
        Draft.objects.create(project_id='project2', from_user_id='fromuser1', to_user_id='touser1')
        url = reverse('draft-list')
        response=self.client.get(url, {'to_user_id': 'touser1'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class UserViewTestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('dukedsuser-list')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fails_not_staff(self):
        self.user.is_staff = False
        self.user.save()
        url = reverse('dukedsuser-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_user(self):
        user_id = django_user.objects.all()[0].pk
        data = {'dds_id': 'abcd-1234-efgh-5678',
                'api_key': 'zxdel8h4g3lvnkqenlf/z',
                'user_id': user_id,
                }
        url = reverse('dukedsuser-list')
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DukeDSUser.objects.count(), 1)
        self.assertEqual(DukeDSUser.objects.get().dds_id, 'abcd-1234-efgh-5678')

    def test_get_users(self):
        DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5679', api_key='zxdel8h4g3lvnkqenl7')
        url = reverse('dukedsuser-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_user(self):
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-detail', args=(u.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dds_id'],'abcd-1234-efgh-5678')

    def test_update_user(self):
        user_id = django_user.objects.all()[0].pk
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-detail', args=(u.pk,))
        data = {'dds_id':'abcd-5555-0000-ffff',
                'api_key':'zxdel8h4g3lvnkqenlf',
                'user_id': user_id
                }
        response = self.client.put(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        u = DukeDSUser.objects.get(pk=u.pk)
        self.assertEqual(u.dds_id,'abcd-5555-0000-ffff')

    def test_delete_user(self):
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-detail', args=(u.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DukeDSUser.objects.count(), 0)

    def test_filter_users(self):
        DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-list')
        response = self.client.get(url, {'dds_id': 'abcd-1234-efgh-5678'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response = self.client.get(url, {'dds_id': 'abcd-1234-efgh-5673'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        # Can't filter on API key,  so this should be ignored
        response = self.client.get(url, {'api_key': 'invalid'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
