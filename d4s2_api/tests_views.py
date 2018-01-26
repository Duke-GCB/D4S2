from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from mock import patch, Mock
from d4s2_api.views import *
from d4s2_api.models import *
from django.contrib.auth.models import User as django_user
from switchboard.mocks_ddsutil import MockDDSProject, MockDDSUser
from gcb_web_auth.tests_dukeds_auth import ResponseStatusCodeTestCase
from rest_framework.test import APIRequestFactory


def setup_mock_ddsutil(mock_ddsutil):
    mock_ddsutil.return_value = Mock()
    mock_ddsutil.return_value.get_remote_user = Mock()
    mock_ddsutil.return_value.get_remote_user.return_value = MockDDSUser('Test User', 'test@example.com')
    mock_ddsutil.return_value.get_remote_project.return_value = MockDDSProject('My Project')
    mock_ddsutil.return_value.create_project_transfer.return_value = {'id': 'mock_ddsutil_transfer_id'}


class AuthenticatedResourceTestCase(APITestCase, ResponseStatusCodeTestCase):
    def setUp(self):
        username = 'api_user'
        password = 'secret'
        self.user = django_user.objects.create_user(username, password=password, is_staff=True)
        self.client.login(username=username, password=password)
        self.ddsuser1 = DukeDSUser.objects.create(user=self.user, dds_id='user1')
        self.ddsuser2 = DukeDSUser.objects.create(dds_id='user2')
        self.transfer_id1 = 'abcd-1234'
        self.transfer_id2 = 'efgh-5678'


class DeliveryViewTestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('delivery-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    @patch('d4s2_api.views.DDSUtil')
    def test_create_delivery(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('delivery-list')
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Delivery.objects.count(), 1)
        self.assertEqual(Delivery.objects.get().from_user_id, 'user1')
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))

    @patch('d4s2_api.views.DDSUtil')
    def test_create_delivery_with_shared_ids(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('delivery-list')
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Delivery.objects.count(), 1)
        self.assertEqual(Delivery.objects.get().from_user_id, 'user1')
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))

    def test_list_deliveries(self):
        Delivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                transfer_id=self.transfer_id1)
        Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                transfer_id=self.transfer_id2)
        url = reverse('delivery-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_delivery(self):
        h = Delivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                    transfer_id=self.transfer_id1)
        url = reverse('delivery-detail', args=(h.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_delivery(self):
        h = Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                    transfer_id=self.transfer_id1)
        url = reverse('delivery-detail', args=(h.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Delivery.objects.count(), 0)

    @patch('d4s2_api.views.DDSUtil')
    def test_update_delivery(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        h = Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                    transfer_id=self.transfer_id1)
        updated = {'from_user_id': self.ddsuser1.dds_id, 'to_user_id': self.ddsuser2.dds_id, 'project_id': 'project3',
                   'transfer_id': h.transfer_id}
        url = reverse('delivery-detail', args=(h.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Delivery.objects.get(pk=h.pk)
        self.assertEqual(h.project_id, 'project3')

    def test_create_delivery_fails_with_transfer_id(self):
        url = reverse('delivery-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'transfer_id': 'transfer123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_deliveries(self):
        h = Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                    transfer_id=self.transfer_id1)
        url = reverse('delivery-list')
        response=self.client.get(url, {'project_id': 'project2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    @patch('d4s2_api.views.DeliveryMessage')
    def test_send_delivery(self, mock_delivery_message):
        instance = mock_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                    transfer_id='abcd')
        self.assertTrue(h.is_new())
        url = reverse('delivery-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = Delivery.objects.get(pk=h.pk)
        self.assertFalse(h.is_new())
        self.assertTrue(mock_delivery_message.called)
        # Make sure transfer_id is in the email message
        ownership_url = reverse('ownership-prompt')
        expected_absolute_url = APIRequestFactory().request().build_absolute_uri(ownership_url) + '?transfer_id=abcd'
        mock_delivery_message.assert_called_with(h, self.user, expected_absolute_url)
        self.assertTrue(instance.send.called)

    @patch('d4s2_api.views.DeliveryMessage')
    def test_send_delivery_fails(self, mock_delivery_message):
        instance = mock_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = Delivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        self.assertTrue(h.is_new())
        h.mark_notified('email text')
        url = reverse('delivery-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_delivery_message.called)
        self.assertFalse(instance.send.called)

    @patch('d4s2_api.views.DDSUtil')
    def test_deliver_with_user_message(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('delivery-list')
        user_message = 'User-specified delivery message'
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'user_message': user_message}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Delivery.objects.count(), 1)
        self.assertEqual(Delivery.objects.get().user_message, user_message)
        # create_project_transfer should be called once
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))


class ShareViewTestCase(AuthenticatedResourceTestCase):

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('share-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_create_share(self):
        url = reverse('share-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'role': 'share_role'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Share.objects.count(), 1)
        self.assertEqual(Share.objects.get().from_user_id, 'user1')
        self.assertEqual(Share.objects.get().role, 'share_role')

    def test_list_shares(self):
        Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2')
        Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        url = reverse('share-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_share(self):
        d =  Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2')
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_share(self):
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Share.objects.count(), 0)

    def test_update_share(self):
        d =  Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        updated = {'project_id': 'project3', 'from_user_id': 'fromuser1', 'to_user_id': 'touser1'}
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d =  Share.objects.get(pk=d.pk)
        self.assertEqual(d.project_id, 'project3')

    @patch('d4s2_api.views.ShareMessage')
    def test_send_share(self, mock_share_message):
        instance = mock_share_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d =  Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        self.assertFalse(d.is_notified())
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Share.objects.get(pk=d.pk)
        self.assertTrue(d.is_notified())
        self.assertTrue(mock_share_message.called)
        self.assertTrue(instance.send.called)

    @patch('d4s2_api.views.ShareMessage')
    def test_send_share_fails(self, mock_share_message):
        instance = mock_share_message.return_value
        instance.send = Mock()
        d =  Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_share_message.called)
        self.assertFalse(instance.send.called)

    @patch('d4s2_api.views.ShareMessage')
    def test_force_send_share(self, mock_share_message):
        instance = mock_share_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d =  Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_share_message.called)
        self.assertTrue(instance.send.called)

    def test_filter_shares(self):
        Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2')
        url = reverse('share-list')
        response=self.client.get(url, {'to_user_id': self.ddsuser2.dds_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_share_with_user_message(self):
        url = reverse('share-list')
        user_message = 'This is a user-specified share message'
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'role': 'share_role', 'user_message': user_message}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Share.objects.count(), 1)
        self.assertEqual(Share.objects.get().user_message, user_message)


