from django.urls import reverse
import rest_framework
from rest_framework.test import APITestCase
from mock import patch, Mock, call
from d4s2_api_v1.api import *
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
        self.dds_id1 = 'user1'
        self.dds_id2 = 'user2'
        self.transfer_id1 = 'abcd-1234'
        self.transfer_id2 = 'efgh-5678'


class DeliveryViewTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        super(DeliveryViewTestCase, self).setUp()
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user, email_template_set=self.email_template_set)

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('ddsdelivery-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_create_delivery(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('ddsdelivery-list')
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        dds_delivery = DDSDelivery.objects.get()
        self.assertEqual(dds_delivery.from_user_id, 'user1')
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))
        self.assertEqual(dds_delivery.email_template_set, self.email_template_set)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_create_delivery_fails_when_user_not_setup(self, mock_ddsutil):
        self.user_email_template_set.delete()
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('ddsdelivery-list')
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [EMAIL_TEMPLATES_NOT_SETUP_MSG])

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_create_delivery_with_shared_ids(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('ddsdelivery-list')
        data = {'project_id': 'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        self.assertEqual(DDSDelivery.objects.get().from_user_id, 'user1')
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))

    def test_list_deliveries(self):
        DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                   transfer_id=self.transfer_id1, email_template_set=self.email_template_set)
        DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                   transfer_id=self.transfer_id2, email_template_set=self.email_template_set)
        url = reverse('ddsdelivery-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_delivery(self):
        h = DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                       transfer_id=self.transfer_id1, email_template_set=self.email_template_set)
        url = reverse('ddsdelivery-detail', args=(h.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_delivery(self):
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id=self.transfer_id1, email_template_set=self.email_template_set)
        url = reverse('ddsdelivery-detail', args=(h.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DDSDelivery.objects.count(), 0)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_update_delivery(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id=self.transfer_id1, email_template_set=self.email_template_set)
        updated = {'from_user_id': self.dds_id1, 'to_user_id': self.dds_id2, 'project_id': 'project3',
                   'transfer_id': h.transfer_id}
        url = reverse('ddsdelivery-detail', args=(h.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = DDSDelivery.objects.get(pk=h.pk)
        self.assertEqual(h.project_id, 'project3')

    def test_create_delivery_fails_with_transfer_id(self):
        url = reverse('ddsdelivery-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'transfer_id': 'transfer123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_deliveries(self):
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id=self.transfer_id1, email_template_set=self.email_template_set)
        url = reverse('ddsdelivery-list')
        response=self.client.get(url, {'project_id': 'project2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response=self.client.get(url, {'project_id': 'project23'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_send_delivery(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id='abcd', email_template_set=self.email_template_set)
        self.assertTrue(h.is_new())
        url = reverse('ddsdelivery-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        h = DDSDelivery.objects.get(pk=h.pk)
        self.assertFalse(h.is_new())
        self.assertTrue(mock_message_factory.return_value.make_delivery_message.called)
        # Make sure transfer_id is in the email message
        ownership_url = reverse('ownership-prompt')
        expected_absolute_url = APIRequestFactory().request().build_absolute_uri(ownership_url) + '?transfer_id=abcd&delivery_type=dds'
        mock_message_factory.return_value.make_delivery_message.assert_called_with(expected_absolute_url)
        self.assertTrue(instance.send.called)

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_send_delivery_with_null_template(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id='abcd', email_template_set=None)
        self.assertTrue(h.is_new())
        url = reverse('ddsdelivery-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG])

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_send_delivery_fails(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        h = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       email_template_set=self.email_template_set)
        self.assertTrue(h.is_new())
        h.mark_notified('email text')
        url = reverse('ddsdelivery-send', args=(h.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_message_factory.return_value.make_delivery_message.called)
        self.assertFalse(instance.send.called)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_deliver_with_user_message(self, mock_ddsutil):
        setup_mock_ddsutil(mock_ddsutil)
        url = reverse('ddsdelivery-list')
        user_message = 'User-specified delivery message'
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'user_message': user_message}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DDSDelivery.objects.count(), 1)
        self.assertEqual(DDSDelivery.objects.get().user_message, user_message)
        # create_project_transfer should be called once
        self.assertEqual(mock_ddsutil.return_value.create_project_transfer.call_count, 1)
        self.assertTrue(mock_ddsutil.return_value.create_project_transfer.called_with('project-id-2', ['user2']))

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_force_send_share(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       email_template_set=self.email_template_set)
        d.mark_notified('email text')
        url = reverse('ddsdelivery-send', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_message_factory.called)
        self.assertTrue(mock_message_factory.return_value.make_delivery_message.called)
        self.assertTrue(instance.send.called)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_cancel_on_accepted(self, mock_ddsutil):
        d = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       email_template_set=self.email_template_set)
        d.mark_accepted('', '')
        url = reverse('ddsdelivery-cancel', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('d4s2_api_v1.api.DDSUtil')
    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_cancel_on_notified(self, mock_message_factory, mock_ddsutil):
        d = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       transfer_id='transfer1', email_template_set=self.email_template_set)
        d.mark_notified('')
        url = reverse('ddsdelivery-cancel', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d.refresh_from_db()
        self.assertEqual(d.state, State.CANCELED)
        mock_ddsutil.return_value.cancel_project_transfer.assert_called_with('transfer1')
        make_canceled_message_func = mock_message_factory.return_value.make_canceled_message
        self.assertTrue(make_canceled_message_func.called)
        self.assertTrue(make_canceled_message_func.return_value.send.called)

    @patch('d4s2_api_v1.api.DDSUtil')
    def test_cancel_with_null_template(self, mock_ddsutil):
        d = DDSDelivery.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                       email_template_set=None)
        d.mark_accepted('', '')
        url = reverse('ddsdelivery-cancel', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG])


class ShareViewTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        super(ShareViewTestCase, self).setUp()
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user, email_template_set=self.email_template_set)

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
        self.assertEqual(Share.objects.get().email_template_set, self.email_template_set)

    def test_create_share_fails_when_user_not_setup(self):
        self.user_email_template_set.delete()
        url = reverse('share-list')
        data = {'project_id':'project-id-2', 'from_user_id': 'user1', 'to_user_id': 'user2', 'role': 'share_role'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [EMAIL_TEMPLATES_NOT_SETUP_MSG])

    def test_list_shares(self):
        Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                             email_template_set=self.email_template_set)
        Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                             email_template_set=self.email_template_set)
        url = reverse('share-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_get_share(self):
        d = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project_id'], 'project1')

    def test_delete_share(self):
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Share.objects.count(), 0)

    def test_update_share(self):
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        updated = {'project_id': 'project3', 'from_user_id': 'fromuser1', 'to_user_id': 'touser1'}
        url = reverse('share-detail', args=(d.pk,))
        response = self.client.put(url, data=updated, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Share.objects.get(pk=d.pk)
        self.assertEqual(d.project_id, 'project3')

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_send_share(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_share_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        instance.send_template_name.return_value = 'deliver'
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        self.assertFalse(d.is_notified())
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        d = Share.objects.get(pk=d.pk)
        self.assertTrue(d.is_notified())
        mock_message_factory.assert_called_with(d, self.user)
        self.assertTrue(instance.send.called)

    def test_send_share_with_null_template(self):
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=None)
        self.assertFalse(d.is_notified())
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG])

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_send_share_fails(self, mock_message_factory):
        instance = mock_message_factory.with_templates_from_user.return_value.make_share_message.return_value
        instance.send = Mock()
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(mock_message_factory.return_value.make_share_message.called)
        self.assertFalse(instance.send.called)

    @patch('d4s2_api_v1.api.DDSMessageFactory')
    def test_force_send_share(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_share_message.return_value
        instance.send = Mock()
        instance.email_text = 'email text'
        d = Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                                 email_template_set=self.email_template_set)
        self.assertFalse(d.is_notified())
        d.mark_notified('email text')
        url = reverse('share-send', args=(d.pk,))
        response = self.client.post(url, data={'force': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_message_factory.assert_called_with(d, self.user)
        self.assertTrue(instance.send.called)

    def test_filter_shares(self):
        Share.objects.create(project_id='project2', from_user_id='user1', to_user_id='user2',
                             email_template_set=self.email_template_set)
        url = reverse('share-list')
        response=self.client.get(url, {'to_user_id': 'user2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        response = self.client.get(url, {'project_id': 'project23'}, format='json')
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


class BuildAcceptUrlTestCase(APITestCase):

    def test_build_accept_url(self):
        request = Mock()
        transfer_id = '123'
        delivery_type = 'test'
        accept_url = build_accept_url(request, transfer_id, delivery_type)
        request.build_absolute_uri.assert_has_calls([call('/ownership/?transfer_id=123&delivery_type=test')])
        self.assertEqual(accept_url, request.build_absolute_uri.return_value)


class ModelWithEmailTemplateSetMixinTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        super(ModelWithEmailTemplateSetMixinTestCase, self).setUp()
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user, email_template_set=self.email_template_set)

    @patch('d4s2_api_v1.api.Response')
    def test_create(self, mock_response):
        mock_serializer = Mock()
        mock_request = Mock(user=self.user, data={})
        mixin = ModelWithEmailTemplateSetMixin()
        mixin.get_serializer = Mock()
        mixin.get_serializer.return_value = mock_serializer
        mixin.get_success_headers = Mock()
        mixin.request = mock_request
        response = mixin.create(request=mock_request)

        self.assertEqual(response, mock_response.return_value)
        mixin.get_serializer.assert_called_with(data=mock_request.data)
        mock_serializer.is_valid.assert_called_with(raise_exception=True)
        mock_serializer.save.assert_called_with(email_template_set=self.email_template_set)
        mock_response.assert_called_with(
            mock_serializer.data, status=status.HTTP_201_CREATED, headers=mixin.get_success_headers.return_value
        )

    def test_get_email_template_for_request(self):
        mixin = ModelWithEmailTemplateSetMixin()
        mixin.request = Mock(user=self.user)
        mixin.request.data = {}
        email_template_set = mixin.get_email_template_for_request()
        self.assertEqual(email_template_set, self.email_template_set)

        self.user_email_template_set.delete()
        with self.assertRaises(rest_framework.exceptions.ValidationError) as raised_exception:
            mixin.get_email_template_for_request()
        self.assertEqual(raised_exception.exception.detail[0], EMAIL_TEMPLATES_NOT_SETUP_MSG)

    @patch('d4s2_api_v1.api.EmailTemplateSet')
    def test_get_email_template_for_request_with_template_set_id(self, mock_email_template_set):
        other_email_template_set = EmailTemplateSet.objects.create(name='otherset')
        mixin = ModelWithEmailTemplateSetMixin()
        mixin.request = Mock(user=self.user)
        mixin.request.data = {'email_template_set_id': other_email_template_set.id}
        email_template_set = mixin.get_email_template_for_request()
        self.assertEqual(email_template_set, mock_email_template_set.get_for_user.return_value.get.return_value)
        mock_email_template_set.get_for_user.assert_called_with(mixin.request.user, 'dds')
        mock_email_template_set.get_for_user.return_value.get.assert_called_with(pk=other_email_template_set.id)

    def test_prevent_null_email_template_set(self):
        mixin = ModelWithEmailTemplateSetMixin()
        mixin.get_object = Mock()
        mixin.get_object.return_value = Mock(email_template_set='something')
        mixin.prevent_null_email_template_set()
        mixin.get_object.return_value = Mock(email_template_set=None)
        with self.assertRaises(rest_framework.exceptions.ValidationError) as raised_exception:
            mixin.prevent_null_email_template_set()
        self.assertEqual(raised_exception.exception.detail[0], ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG)
