from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.auth.models import User as django_user
from rest_framework import status
from rest_framework.test import APITestCase
from d4s2_api_v1.tests_api import AuthenticatedResourceTestCase
from mock import patch, Mock
from d4s2_api.models import *
from mock import call
from switchboard.s3_util import S3Exception, S3NoSuchBucket


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
        delivery = DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                              transfer_id='transfer1')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user4')

        DDSDelivery.objects.create(project_id='project2', from_user_id='user5', to_user_id='user1',
                                   transfer_id='transfer2')

        delivery3 = DDSDelivery.objects.create(project_id='project4', from_user_id='user1', to_user_id='user6',
                                               transfer_id='transfer3')
        # share with self after delivery
        DDSDeliveryShareUser.objects.create(delivery=delivery3, dds_id='user1')

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
        delivery = DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                           transfer_id='transfer1')
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
        self.assertEqual(transfer['delivery'], str(delivery.id))

        transfer = response.data[1]
        self.assertEqual(transfer['id'], 'transfer2')
        self.assertEqual(transfer['status'], 'accepted')
        self.assertEqual(transfer['status_comment'], None)
        self.assertEqual(len(transfer['to_users']), 1)
        self.assertEqual(transfer['to_users'][0]['id'], 'user1')
        self.assertEqual(transfer['from_user']['id'], 'user3')
        self.assertEqual(transfer['project']['name'], 'Rat')
        self.assertEqual(transfer['delivery'], None)

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


class UserLogin(object):
    """
    Wraps up different user states for tests.
    """
    def __init__(self, client):
        self.client = client

    def become_unauthorized(self):
        self.client.logout()

    def become_normal_user(self):
        username = "user"
        password = "resu"
        email = "user@resu.com"
        user = django_user.objects.create_user(username=username, password=password, email=email)
        self.client.login(username=username, password=password)
        return user

    def become_other_normal_user(self):
        username = "user2"
        password = "resu2"
        email = "user2@resu2.com"
        user = django_user.objects.create_user(username=username, password=password, email=email)
        self.client.login(username=username, password=password)
        return user

    def become_third_normal_user(self):
        username = "user3"
        password = "resu3"
        email = "user3@resu3.com"
        user = django_user.objects.create_user(username=username, password=password, email=email)
        self.client.login(username=username, password=password)
        return user

    def become_admin_user(self):
        username = "myadmin"
        password = "nimda"
        user = django_user.objects.create_superuser(username=username, email='', password=password)
        self.client.login(username=username, password=password)
        return user


class UserTestCase(APITestCase):

    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.mock_user = Mock()
        self.mock_user.id = '123-414-123'

    def test_requires_login(self):
        self.user_login.become_unauthorized()
        url = reverse('v2-user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_list(self):
        with self.assertRaises(NoReverseMatch):
            reverse('v2-user-list')

    @patch('d4s2_api_v2.serializers.DDSUtil')
    def test_get_current_user(self, mock_dds_util):
        mock_dds_util.return_value.get_current_user.return_value = self.mock_user
        self.user_login.become_normal_user()
        url = reverse('v2-user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user')

        self.user_login.become_other_normal_user()
        url = reverse('v2-user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user2')

    def test_cannot_change(self):
        self.user_login.become_normal_user()
        url = reverse('v2-user-current-user')
        response = self.client.put(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response = self.client.delete(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.serializers.DDSUtil')
    def test_cannot_get_by_id(self, mock_dds_util):
        mock_dds_util.return_value.get_current_user.return_value = self.mock_user
        self.user_login.become_normal_user()
        url = reverse('v2-user-current-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user')
        user_id = response.data['id']
        self.assertIsNotNone(django_user.objects.get(id=user_id))
        detail_url = '{}/{}'.format(url, user_id)
        response = self.client.get(detail_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class S3EndpointViewSetTestCase(AuthenticatedResourceTestCase):
    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-s3endpoint-list')
        response = self.client.get(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-s3endpoint-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-s3endpoint-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_endpoints(self):
        S3Endpoint.objects.create(url='http://s3.com', name='com')
        S3Endpoint.objects.create(url='http://s3.org', name='org')
        S3Endpoint.objects.create(url='http://s3.net', name='net')

        url = reverse('v2-s3endpoint-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(set([endpoint['url'] for endpoint in response.data]),
                         set(['http://s3.com', 'http://s3.org', 'http://s3.net']))
        self.assertEqual(set([endpoint['name'] for endpoint in response.data]),
                         set(['com', 'org', 'net']))

    def test_list_endpoint_filter_by_name(self):
        S3Endpoint.objects.create(url='http://s3.com', name='com')
        S3Endpoint.objects.create(url='http://s3.org', name='org')
        S3Endpoint.objects.create(url='http://s3.net', name='net')

        url = reverse('v2-s3endpoint-list') + "?name=org"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'org')
        self.assertEqual(response.data[0]['url'], 'http://s3.org')


class S3UserViewSetTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.endpoint = S3Endpoint.objects.create(url='http://s3.com', name='primary')
        self.normal_user1 = self.user_login.become_normal_user()
        self.normal_user2 = self.user_login.become_other_normal_user()

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-s3user-list')
        response = self.client.get(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-s3user-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-s3user-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_s3users(self):
        s3_user1 = S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)
        s3_user2 = S3User.objects.create(endpoint=self.endpoint, s3_id='def', user=self.normal_user2)

        expected_data = {
            s3_user1.id: {
                'email': s3_user1.user.email,
                'type': 'Normal'
            },
            s3_user2.id: {
                'email': s3_user2.user.email,
                'type': 'Normal'
            }
        }

        url = reverse('v2-s3user-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        for s3_user_resp in response.data:
            s3_id = s3_user_resp['id']
            expected_dict = expected_data[s3_id]
            self.assertEqual(s3_user_resp['email'], expected_dict['email'])
            self.assertEqual(s3_user_resp['type'], expected_dict['type'])

    def test_list_s3users_hides_agents(self):
        s3_user1 = S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)
        S3User.objects.create(endpoint=self.endpoint, s3_id='def', user=self.normal_user2, type=S3UserTypes.AGENT)

        expected_data = {
            s3_user1.id: {
                'email': s3_user1.user.email,
                'type': 'Normal'
            },
        }

        url = reverse('v2-s3user-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        for s3_user_resp in response.data:
            s3_id = s3_user_resp['id']
            expected_dict = expected_data[s3_id]
            self.assertEqual(s3_user_resp['email'], expected_dict['email'])
            self.assertEqual(s3_user_resp['type'], expected_dict['type'])

    def test_list_s3users_email_filter(self):
        S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)
        s3_user2 = S3User.objects.create(endpoint=self.endpoint, s3_id='def', user=self.normal_user2)

        expected_data = {
            s3_user2.id: {
                'email': s3_user2.user.email,
                'type': 'Normal'
            }
        }

        url = reverse('v2-s3user-list') + '?email=' + s3_user2.user.email
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        for s3_user_resp in response.data:
            s3_id = s3_user_resp['id']
            expected_dict = expected_data[s3_id]
            self.assertEqual(s3_user_resp['email'], expected_dict['email'])
            self.assertEqual(s3_user_resp['type'], expected_dict['type'])

    def test_list_s3users_endpoint_user_filtering(self):
        endpoint2 = S3Endpoint.objects.create(url='http://s4.com', name='other')
        s3_user1 = S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)
        s3_user2 = S3User.objects.create(endpoint=self.endpoint, s3_id='def', user=self.normal_user2)
        s3_user2 = S3User.objects.create(endpoint=endpoint2, s3_id='def', user=self.normal_user2)

        expected_data = {
            s3_user2.id: {
                'email': s3_user2.user.email,
                'type': 'Normal',
                'endpoint': endpoint2.id,
            }
        }

        url = reverse('v2-s3user-list') + '?user={}&endpoint={}'.format(self.normal_user2.id, endpoint2.id)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        for s3_user_resp in response.data:
            s3_id = s3_user_resp['id']
            expected_dict = expected_data[s3_id]
            self.assertEqual(s3_user_resp['email'], expected_dict['email'])
            self.assertEqual(s3_user_resp['type'], expected_dict['type'])


class S3BucketViewSetTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        self.user_login = UserLogin(self.client)
        self.endpoint = S3Endpoint.objects.create(url='http://s3.com')
        self.normal_user1 = self.user_login.become_normal_user()
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-s3bucket-list')
        response = self.client.get(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_list_s3buckets_shows_owned_buckets(self):
        bucket = S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        url = reverse('v2-s3bucket-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        bucket_response = response.data[0]
        self.assertEqual(bucket_response['id'], bucket.id)
        self.assertEqual(bucket_response['name'], 'mouse1')
        self.assertEqual(bucket_response['owner'], self.s3_user1.id)
        self.assertEqual(bucket_response['endpoint'], self.endpoint.id)

    def test_list_s3buckets_filters_by_name(self):
        S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        bucket2 = S3Bucket.objects.create(name='mouse2', owner=self.s3_user1, endpoint=self.endpoint)
        url = reverse('v2-s3bucket-list') + "?name=mouse2"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        bucket_response = response.data[0]
        self.assertEqual(bucket_response['id'], bucket2.id)
        self.assertEqual(bucket_response['name'], 'mouse2')
        self.assertEqual(bucket_response['owner'], self.s3_user1.id)
        self.assertEqual(bucket_response['endpoint'], self.endpoint.id)

    def test_list_s3buckets_hides_from_other_users(self):
        S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        self.user_login.become_other_normal_user()

        url = reverse('v2-s3bucket-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_s3buckets_shown_to_other_users_receiving_deliveries(self):
        bucket = S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        other_normal_user = self.user_login.become_other_normal_user()
        s3_other_user = S3User.objects.create(endpoint=self.endpoint, s3_id='cde', user=other_normal_user)
        S3Delivery.objects.create(bucket=bucket, from_user=self.s3_user1, to_user=s3_other_user)

        url = reverse('v2-s3bucket-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        bucket_response = response.data[0]
        self.assertEqual(bucket_response['id'], bucket.id)
        self.assertEqual(bucket_response['name'], 'mouse1')
        self.assertEqual(bucket_response['owner'], self.s3_user1.id)
        self.assertEqual(bucket_response['endpoint'], self.endpoint.id)

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_create_s3_buckets(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.return_value = True
        url = reverse('v2-s3bucket-list')
        data = {'name': 'mouse2', 'owner': self.s3_user1.id, 'endpoint': self.endpoint.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bucket = S3Bucket.objects.get(name='mouse2')
        self.assertEqual(bucket.owner, self.s3_user1)
        mock_s3_bucket_util.return_value.user_owns_bucket.assert_called_with('mouse2')

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_create_s3_buckets_if_not_owner_in_s3(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.return_value = False
        url = reverse('v2-s3bucket-list')
        data = {'name': 'mouse2', 'owner': self.s3_user1.id, 'endpoint': self.endpoint.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Your user do not own bucket mouse2.')
        self.assertEqual(S3Bucket.objects.count(), 0)

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_create_s3_buckets_if_not_found_in_s3(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.side_effect = S3NoSuchBucket('No such bucket')
        url = reverse('v2-s3bucket-list')
        data = {'name': 'mouse2', 'owner': self.s3_user1.id, 'endpoint': self.endpoint.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'No such bucket')
        self.assertEqual(S3Bucket.objects.count(), 0)

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_create_s3_buckets_if_not_owner(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.return_value = True
        url = reverse('v2-s3bucket-list')
        data = {'name': 'mouse2', 'owner': self.s3_user1.id, 'endpoint': self.endpoint.id}
        self.user_login.become_other_normal_user()
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_put_s3_bucket(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.return_value = True
        bucket = S3Bucket.objects.create(name='mouseOops', owner=self.s3_user1, endpoint=self.endpoint)
        url = reverse('v2-s3bucket-list') + str(bucket.id) + '/'
        data = {'name': 'mouseFixed', 'owner': bucket.owner.id, 'endpoint': bucket.endpoint.id}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(S3Bucket.objects.get(pk=bucket.id).name, 'mouseFixed')

    @patch('d4s2_api_v2.api.S3BucketUtil')
    def test_put_s3_bucket_if_not_owner_in_s3(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.user_owns_bucket.return_value = False
        bucket = S3Bucket.objects.create(name='mouseOops', owner=self.s3_user1, endpoint=self.endpoint)
        url = reverse('v2-s3bucket-list') + str(bucket.id) + '/'
        data = {'name': 'mouseFixed', 'owner': bucket.owner.id, 'endpoint': bucket.endpoint.id}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_own_s3_buckets(self):
        bucket = S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        url = reverse('v2-s3bucket-list') + str(bucket.id) + '/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_own_s3_buckets(self):
        bucket = S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        self.user_login.become_other_normal_user()
        url = reverse('v2-s3bucket-list') + str(bucket.id) + '/'
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class S3DeliveryViewSetTestCase(APITestCase):
    def setUp(self):
        # create some django users
        self.normal_user1 = user = django_user.objects.create_user(username='user1', password='user1')
        self.normal_user2 = user = django_user.objects.create_user(username='user2', password='user2')
        self.normal_user3 = user = django_user.objects.create_user(username='user3', password='user3')

        # create and endpoint and some S3Users
        self.endpoint = S3Endpoint.objects.create(url='http://s1.com', name='s1')
        self.endpoint2 = S3Endpoint.objects.create(url='http://s2.com', name='s2')
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint, s3_id='abc', user=self.normal_user1)
        self.s3_user2 = S3User.objects.create(endpoint=self.endpoint, s3_id='def', user=self.normal_user2)
        self.s3_user3 = S3User.objects.create(endpoint=self.endpoint, s3_id='hij', user=self.normal_user3)
        self.other_endpoint_s3_user = S3User.objects.create(endpoint=self.endpoint2, s3_id='klm',
                                                            user=self.normal_user3)

        # create some buckets
        self.mouse1_bucket = S3Bucket.objects.create(name='mouse1', owner=self.s3_user1, endpoint=self.endpoint)
        self.mouse2_bucket = S3Bucket.objects.create(name='mouse2', owner=self.s3_user1, endpoint=self.endpoint)
        self.mouse3_bucket = S3Bucket.objects.create(name='mouse3', owner=self.s3_user2, endpoint=self.endpoint)
        self.other_endpoint_bucket = S3Bucket.objects.create(name='otherEndpointBucket',
                                                             owner=self.other_endpoint_s3_user,
                                                             endpoint=self.endpoint2)

    def login_user1(self):
        self.client.login(username='user1', password='user1')

    def login_user2(self):
        self.client.login(username='user2', password='user2')

    def login_user3(self):
        self.client.login(username='user3', password='user3')

    def test_fails_unauthenticated(self):
        url = reverse('v2-s3delivery-list')
        response = self.client.get(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_deliveries(self):
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2)
        self.login_user1()
        url = reverse('v2-s3delivery-list')
        response = self.client.get(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        delivery_response = response.data[0]
        self.assertEqual(delivery_response['id'], delivery.id)
        self.assertEqual(delivery_response['bucket'], self.mouse1_bucket.id)
        self.assertEqual(delivery_response['from_user'], self.s3_user1.id)
        self.assertEqual(delivery_response['to_user'], self.s3_user2.id)
        self.assertEqual(delivery_response['state'], State.NEW)

    def test_list_deliveries_seen_by_to_from_users(self):
        S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2)

        self.login_user1()
        url = reverse('v2-s3delivery-list')
        response = self.client.get(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        self.login_user2()
        url = reverse('v2-s3delivery-list')
        response = self.client.get(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        self.login_user3()
        url = reverse('v2-s3delivery-list')
        response = self.client.get(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_delivery_only_as_from_user(self):
        self.login_user1()
        url = reverse('v2-s3delivery-list')
        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.s3_user1.id,
            'to_user': self.s3_user2.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        s3_deliveries = S3Delivery.objects.all()
        self.assertEqual(len(s3_deliveries), 1)
        self.assertEqual(s3_deliveries[0].bucket, self.mouse1_bucket)

        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.s3_user2.id,
            'to_user': self.s3_user1.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_delivery_with_mismatched_endpoints(self):
        self.login_user1()
        url = reverse('v2-s3delivery-list')
        data = {
            'bucket': self.other_endpoint_bucket.id,
            'from_user': self.s3_user1.id,
            'to_user': self.s3_user2.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.other_endpoint_s3_user.id,
            'to_user': self.s3_user2.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.s3_user1.id,
            'to_user': self.other_endpoint_s3_user.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('d4s2_api_v2.api.build_accept_url')
    @patch('d4s2_api_v2.api.S3DeliveryUtil')
    @patch('d4s2_api_v2.api.S3BucketUtil')
    @patch('d4s2_api_v2.api.S3MessageFactory')
    def test_send_delivery(self, mock_s3_message_factory, mock_s3_bucket_util, mock_s3_delivery_util,
                           mock_build_accept_url):
        mock_s3_message_factory.return_value.make_delivery_message.return_value = Mock(email_text='email text')
        mock_s3_bucket_util.return_value.get_objects_manifest.return_value = [{'meta': '123'}]
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2)
        self.login_user1()
        url = reverse('v2-s3delivery-list') + str(delivery.id) + '/send/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_s3_delivery_util.return_value.give_agent_permissions.called, True)
        delivery = S3Delivery.objects.get(pk=delivery.id)
        self.assertEqual(delivery.state, State.NOTIFIED)
        self.assertEqual(delivery.delivery_email_text, 'email text')
        self.assertEqual(delivery.manifest.content, [{"meta": "123"}])
        mock_s3_message_factory.assert_called_with(delivery, self.normal_user1)
        mock_s3_message_factory.return_value.make_delivery_message.assert_called_with(
            mock_build_accept_url.return_value)

    @patch('d4s2_api_v2.api.S3DeliveryUtil')
    @patch('d4s2_api_v2.api.S3BucketUtil')
    @patch('d4s2_api_v2.api.S3MessageFactory')
    def test_send_delivery_s3_exception(self, mock_s3_message_factory, mock_s3_bucket_util, mock_s3_delivery_util):
        mock_s3_delivery_util.return_value.give_agent_permissions.side_effect = S3Exception('test')
        mock_s3_bucket_util.return_value.get_objects_manifest.return_value = [{'meta': '123'}]
        mock_s3_message_factory.return_value.make_delivery_message.return_value = Mock(email_text='email text')
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2)
        self.login_user1()
        url = reverse('v2-s3delivery-list') + str(delivery.id) + '/send/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {'detail': 'test'})
