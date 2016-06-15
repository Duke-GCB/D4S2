from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from mock import patch, Mock
from handover_api.views import *
from handover_api.models import *
from django.contrib.auth.models import User as django_user
from ownership.test_views import MockDDSUser


class AuthenticatedResourceTestCase(APITestCase):
    def setUp(self):
        username = 'api_user'
        password = 'secret'
        self.user = django_user.objects.create_user(username, password=password, is_staff=True)
        self.client.login(username=username, password=password)
        self.ddsuser1 = DukeDSUser.objects.create(user=self.user, dds_id='user1')
        self.ddsuser2 = DukeDSUser.objects.create(dds_id='user2')
        self.project1 = DukeDSProject.objects.create(project_id='project1', name='Project 1')
        self.project2 = DukeDSProject.objects.create(project_id='project2', name='Project 2')


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
        self.assertEqual(Handover.objects.get().from_user.dds_id, 'user1')

    def test_list_handovers(self):
        Handover.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2)
        Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('handover-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_handover(self):
        h = Handover.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_handover(self):
        h = Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Handover.objects.count(), 0)

    def test_update_handover(self):
        h = Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        DukeDSProject.objects.create(project_id='project3')
        updated = {'from_user_id': self.ddsuser1.dds_id, 'to_user_id': self.ddsuser2.dds_id ,'project_id': 'project3'}
        url = reverse('handover-detail', args=(h.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Handover.objects.get(pk=h.pk)
        self.assertEqual(h.project.project_id, 'project3')

    def test_filter_handovers(self):
        h = Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('handover-list')
        response=self.client.get(url, {'project_id': 'project2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    @patch('handover_api.views.HandoverMessage')
    def test_send_handover(self, mock_handover_message):
        instance = mock_handover_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        self.assertTrue(h.is_new())
        url = reverse('handover-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Handover.objects.get(pk=h.pk)
        self.assertFalse(h.is_new())
        self.assertTrue(mock_handover_message.called)
        self.assertTrue(instance.send.called)

    @patch('handover_api.views.HandoverMessage')
    def test_send_handover_fails(self, mock_handover_message):
        instance = mock_handover_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = Handover.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        self.assertTrue(h.is_new())
        h.mark_notified('email text')
        url = reverse('handover-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_handover_message.called)
        self.assertFalse(instance.send.called)


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
        self.assertEqual(Draft.objects.get().from_user.dds_id, 'user1')

    def test_list_drafts(self):
        Draft.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2)
        Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('draft-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_draft(self):
        d =  Draft.objects.create(project=self.project1, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_draft(self):
        d =  Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Draft.objects.count(), 0)

    def test_update_draft(self):
        d =  Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        updated = {'project_id': 'project3', 'from_user_id': 'fromuser1', 'to_user_id':'touser1'}
        url = reverse('draft-detail', args=(d.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d =  Draft.objects.get(pk=d.pk)
        self.assertEqual(d.project.project_id, 'project3')

    @patch('handover_api.views.DraftMessage')
    def test_send_draft(self, mock_draft_message):
        instance = mock_draft_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d =  Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        self.assertFalse(d.is_notified())
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Draft.objects.get(pk=d.pk)
        self.assertTrue(d.is_notified())
        self.assertTrue(mock_draft_message.called)
        self.assertTrue(instance.send.called)

    @patch('handover_api.views.DraftMessage')
    def test_send_draft_fails(self, mock_draft_message):
        instance = mock_draft_message.return_value
        instance.send = Mock()
        d =  Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_draft_message.called)
        self.assertFalse(instance.send.called)

    @patch('handover_api.views.DraftMessage')
    def test_force_send_draft(self, mock_draft_message):
        instance = mock_draft_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d =  Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('draft-send', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_draft_message.called)
        self.assertTrue(instance.send.called)

    def test_filter_drafts(self):
        Draft.objects.create(project=self.project2, from_user=self.ddsuser1, to_user=self.ddsuser2)
        url = reverse('draft-list')
        response=self.client.get(url, {'to_user_id': self.ddsuser2.dds_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = Mock()
    mock_ddsutil.return_value.get_remote_user = Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser('Test User', 'test@test.com')


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

    @patch('handover_api.views.DDSUtil')
    def test_create_user(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        initial_count = DukeDSUser.objects.count()
        new_django_user = django_user.objects.create_user('new_django_user')
        data = {'dds_id': 'abcd-1234-efgh-5678',
                'api_key': 'zxdel8h4g3lvnkqenlf/z',
                'user_id': new_django_user.pk,
                }
        url = reverse('dukedsuser-list')
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DukeDSUser.objects.count(), initial_count + 1)
        self.assertEqual(DukeDSUser.objects.get(user_id=new_django_user.pk).dds_id, 'abcd-1234-efgh-5678')

    def test_get_users(self):
        initial_count = DukeDSUser.objects.count()
        DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5679', api_key='zxdel8h4g3lvnkqenl7')
        url = reverse('dukedsuser-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), initial_count + 2)

    def test_get_user(self):
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-detail', args=(u.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dds_id'],'abcd-1234-efgh-5678')

    @patch('handover_api.views.DDSUtil')
    def test_update_user(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        # Initially with no django user attached
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        url = reverse('dukedsuser-detail', args=(u.pk,))
        new_django_user = django_user.objects.create_user('new_django_user')
        data = {'dds_id':'abcd-5555-0000-ffff',
                'api_key':'zxdel8h4g3lvnkqenlf',
                'user_id': new_django_user.pk
                }
        response = self.client.put(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        u = DukeDSUser.objects.get(pk=u.pk)
        self.assertEqual(u.dds_id,'abcd-5555-0000-ffff')

    def test_delete_user(self):
        initial_count = DukeDSUser.objects.count()
        u = DukeDSUser.objects.create(dds_id='abcd-1234-efgh-5678', api_key='zxdel8h4g3lvnkqenlf')
        self.assertEqual(DukeDSUser.objects.count(), initial_count + 1)
        url = reverse('dukedsuser-detail', args=(u.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DukeDSUser.objects.count(), initial_count)

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
        self.assertEqual(len(response.data), DukeDSUser.objects.count())
