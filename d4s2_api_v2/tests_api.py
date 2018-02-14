from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from d4s2_api.tests_views import AuthenticatedResourceTestCase
from mock import patch, Mock
from d4s2_api.views import *
from d4s2_api.models import *
from mock import call


class DDSUsersViewSetTestCase(AuthenticatedResourceTestCase):
    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-dukedsuser-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-dukedsuser-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-dukedsuser-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_users(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'user1',
                    'username': 'joe1',
                    'full_name': 'Joseph Smith',
                    'email': 'joe@joe.joe',
                }, {
                    'id': 'user2',
                    'username': 'bob1',
                    'full_name': 'Robert Doe',
                    'email': 'bob@bob.bob',
                }
            ]
        }
        mock_dds_util.return_value.get_users.return_value = mock_response
        url = reverse('v2-dukedsuser-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        user = response.data[0]
        self.assertEqual(user['id'], 'user1')
        self.assertEqual(user['username'], 'joe1')
        self.assertEqual(user['full_name'], 'Joseph Smith')
        self.assertEqual(user['email'], 'joe@joe.joe')

        user = response.data[1]
        self.assertEqual(user['id'], 'user2')
        self.assertEqual(user['username'], 'bob1')
        self.assertEqual(user['full_name'], 'Robert Doe')
        self.assertEqual(user['email'], 'bob@bob.bob')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_users_with_full_name_contains(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'user1',
                    'username': 'joe1',
                    'full_name': 'Joseph Smith',
                    'email': 'joe@joe.joe',
                }
            ]
        }
        mock_dds_util.return_value.get_users.return_value = mock_response
        url = reverse('v2-dukedsuser-list') + '?full_name_contains=smith'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        mock_dds_util.return_value.get_users.assert_called_with("smith")

        user = response.data[0]
        self.assertEqual(user['id'], 'user1')
        self.assertEqual(user['username'], 'joe1')
        self.assertEqual(user['full_name'], 'Joseph Smith')
        self.assertEqual(user['email'], 'joe@joe.joe')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_users_with_recent_and_full_name_contains(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'user1',
                    'username': 'joe1',
                    'full_name': 'Joseph Smith',
                    'email': 'joe@joe.joe',
                }
            ]
        }
        mock_dds_util.return_value.get_users.return_value = mock_response
        url = reverse('v2-dukedsuser-list') + '?recent=true&full_name_contains=smith'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_users_with_recent(self, mock_dds_util):
        delivery = Delivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                           transfer_id='transfer1')
        DeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')
        DeliveryShareUser.objects.create(delivery=delivery, dds_id='user4')

        Delivery.objects.create(project_id='project2', from_user_id='user5', to_user_id='user1',
                                transfer_id='transfer2')

        delivery3 = Delivery.objects.create(project_id='project4', from_user_id='user1', to_user_id='user6',
                                            transfer_id='transfer3')
        # share with self after delivery
        DeliveryShareUser.objects.create(delivery=delivery3, dds_id='user1')

        mock_current_user = Mock()
        mock_current_user.id = 'user1'
        mock_dds_util.return_value.get_current_user.return_value = mock_current_user
        mock_user2 = Mock()
        mock_user2.json.return_value = {'full_name': 'Joe'}
        mock_user3 = Mock()
        mock_user3.json.return_value = {'full_name': 'Jim'}
        mock_user4 = Mock()
        mock_user4.json.return_value = {'full_name': 'Bob'}
        mock_user6 = Mock()
        mock_user6.json.return_value = {'full_name': 'Dan'}
        mock_share_users = [
            mock_user2,
            mock_user3,
            mock_user4,
            mock_user6,
        ]
        mock_dds_util.return_value.get_user.side_effect = mock_share_users
        url = reverse('v2-dukedsuser-list') + '?recent=true'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # We should have fetch user details for only users who we have shared with
        mock_dds_util.return_value.get_user.assert_has_calls([
            call('user2'),  call('user3'), call('user4'), call('user6'),
        ], any_order=True)

        self.assertEqual(len(response.data), 4)
        full_names = [user['full_name'] for user in response.data]
        self.assertEqual(full_names, ['Joe', 'Jim', 'Bob', 'Dan'])

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_get_user(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'user1',
            'username': 'joe1',
            'full_name': 'Joseph Smith',
            'email': 'joe@joe.joe',
        }
        mock_dds_util.return_value.get_user.return_value = mock_response
        url = reverse('v2-dukedsuser-list') + 'user1/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_dds_util.return_value.get_user.assert_called_with('user1')

        user = response.data
        self.assertEqual(user['id'], 'user1')
        self.assertEqual(user['username'], 'joe1')
        self.assertEqual(user['full_name'], 'Joseph Smith')
        self.assertEqual(user['email'], 'joe@joe.joe')


class DDSProjectsViewSetTestCase(AuthenticatedResourceTestCase):
    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-dukedsproject-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-dukedsproject-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-dukedsproject-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_projects(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'project1',
                    'name': 'Mouse',
                    'description': 'Mouse RNA',
                }, {
                    'id': 'project2',
                    'name': 'Turtle',
                    'description': 'Turtle DNA',
                }
            ]
        }
        mock_dds_util.return_value.get_projects.return_value = mock_response
        url = reverse('v2-dukedsproject-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        project = response.data[0]
        self.assertEqual(project['id'], 'project1')
        self.assertEqual(project['name'], 'Mouse')
        self.assertEqual(project['description'], 'Mouse RNA')

        project = response.data[1]
        self.assertEqual(project['id'], 'project2')
        self.assertEqual(project['name'], 'Turtle')
        self.assertEqual(project['description'], 'Turtle DNA')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_get_project(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'project1',
            'name': 'Mouse',
            'description': 'Mouse RNA',
        }
        mock_dds_util.return_value.get_project.return_value = mock_response
        url = reverse('v2-dukedsproject-list') + 'project1/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_dds_util.return_value.get_project.assert_called_with('project1')

        project = response.data
        self.assertEqual(project['id'], 'project1')
        self.assertEqual(project['name'], 'Mouse')
        self.assertEqual(project['description'], 'Mouse RNA')


class DDSProjectTransfersViewSetTestCase(AuthenticatedResourceTestCase):
    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-dukedsprojecttransfer-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-dukedsprojecttransfer-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-dukedsprojecttransfer-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_transfers(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'transfer1',
                    'status': 'pending',
                    'status_comment': 'Some status comment',
                    'to_users': [
                        {
                            'id': 'user1',
                            'username': 'joe',
                            'full_name': 'Joe Bob'
                        }
                    ],
                    'from_user': {
                        'id': 'user2',
                        'username': 'jim',
                        'full_name': 'Jim Bob'
                    },
                    'project': {
                        'id': 'project1',
                        'name': 'Mouse'
                    }
                }, {
                    'id': 'transfer2',
                    'status': 'accepted',
                    'status_comment': None,
                    'to_users': [
                        {
                            'id': 'user1',
                            'username': 'joe',
                            'full_name': 'Joe Bob'
                        }
                    ],
                    'from_user': {
                        'id': 'user3',
                        'username': 'jane',
                        'full_name': 'Jane Bob'
                    },
                    'project': {
                        'id': 'project2',
                        'name': 'Rat'
                    }
                }
            ]
        }
        mock_dds_util.return_value.get_project_transfers.return_value = mock_response
        url = reverse('v2-dukedsprojecttransfer-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        transfer = response.data[0]
        self.assertEqual(transfer['id'], 'transfer1')
        self.assertEqual(transfer['status'], 'pending')
        self.assertEqual(transfer['status_comment'], 'Some status comment')
        self.assertEqual(len(transfer['to_users']), 1)
        self.assertEqual(transfer['to_users'][0]['id'], 'user1')
        self.assertEqual(transfer['from_user']['id'], 'user2')
        self.assertEqual(transfer['project']['name'], 'Mouse')

        transfer = response.data[1]
        self.assertEqual(transfer['id'], 'transfer2')
        self.assertEqual(transfer['status'], 'accepted')
        self.assertEqual(transfer['status_comment'], None)
        self.assertEqual(len(transfer['to_users']), 1)
        self.assertEqual(transfer['to_users'][0]['id'], 'user1')
        self.assertEqual(transfer['from_user']['id'], 'user3')
        self.assertEqual(transfer['project']['name'], 'Rat')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_get_project(self, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'transfer1',
            'status': 'pending',
            'status_comment': 'Some status comment',
            'to_users': [
                {
                    'id': 'user1',
                    'username': 'joe',
                    'full_name': 'Joe Bob'
                }
            ],
            'from_user': {
                'id': 'user2',
                'username': 'jim',
                'full_name': 'Jim Bob'
            },
            'project': {
                'id': 'project1',
                'name': 'Mouse'
            }
        }
        mock_dds_util.return_value.get_project_transfer.return_value = mock_response
        url = reverse('v2-dukedsprojecttransfer-list') + 'transfer1/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_dds_util.return_value.get_project_transfer.assert_called_with('transfer1')

        transfer = response.data
        self.assertEqual(transfer['id'], 'transfer1')
        self.assertEqual(transfer['status'], 'pending')
        self.assertEqual(transfer['status_comment'], 'Some status comment')
        self.assertEqual(len(transfer['to_users']), 1)
        self.assertEqual(transfer['to_users'][0]['id'], 'user1')
        self.assertEqual(transfer['from_user']['id'], 'user2')
        self.assertEqual(transfer['project']['name'], 'Mouse')
