from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.auth.models import User as django_user
from rest_framework import status
from rest_framework.test import APITestCase
from d4s2_api_v1.tests_api import AuthenticatedResourceTestCase
from d4s2_api_v1.api import EMAIL_TEMPLATES_NOT_SETUP_MSG, CANNOT_PASS_EMAIL_TEMPLATE_SET, \
    ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG
from mock import patch, Mock, MagicMock
from d4s2_api.models import *
from mock import call
from switchboard.s3_util import S3Exception, S3NoSuchBucket
from switchboard.dds_util import DDSAuthProvider, DDSAffiliate, DDSUser, DataServiceError
from switchboard.azure_util import AzureProjectSummary
from gcb_web_auth.models import GroupManagerConnection
from switchboard import userservice
from django.core.signing import Signer
from django.contrib.auth.models import Group
import json


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
        mock_dds_util.return_value.get_users.assert_called_with("smith", None, None)

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
        email_template_set = EmailTemplateSet.objects.create(name='someset')
        delivery = DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                              transfer_id='transfer1', email_template_set=email_template_set)
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user4')

        DDSDelivery.objects.create(project_id='project2', from_user_id='user5', to_user_id='user1',
                                   transfer_id='transfer2', email_template_set=email_template_set)

        delivery3 = DDSDelivery.objects.create(project_id='project4', from_user_id='user1', to_user_id='user6',
                                               transfer_id='transfer3', email_template_set=email_template_set)
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

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_current_dds_user(self, mock_dds_util):
        mock_current_user = Mock(
            id='current-user-id',
            username='joe1',
            full_name='Joseph Smith',
            email='joe@joe.joe',
            first_name='Joe',
            last_name='Smith'
        )
        mock_dds_util.return_value.get_current_user.return_value = mock_current_user

        url = reverse('v2-dukedsuser-current-duke-ds-user')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Assert that get_current_user was called to identify the current user
        self.assertTrue(mock_dds_util.return_value.get_current_user.called)
        self.assertEqual(mock_dds_util.return_value.get_current_user.call_count, 1)

        user = response.data
        self.assertEqual(user['id'], 'current-user-id')
        self.assertEqual(user['username'], 'joe1')
        self.assertEqual(user['full_name'], 'Joseph Smith')
        self.assertEqual(user['email'], 'joe@joe.joe')
        self.assertEqual(user['first_name'], 'Joe')
        self.assertEqual(user['last_name'], 'Smith')


class MockDataServiceError(DataServiceError):

    def __init__(self, status_code):
        self.status_code = status_code
        self.response = None


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
    @patch('d4s2_api_v2.api.DDSUtil.get_project_url')
    def test_list_projects(self, mock_get_project_url, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'project1',
                    'name': 'Mouse',
                    'description': 'Mouse RNA',
                    'is_deleted': False,
                    'audit': {
                        'created_on': '2019-01-01',
                        'last_updated_on': '2019-06-01'
                    }
                }, {
                    'id': 'project2',
                    'name': 'Turtle',
                    'description': 'Turtle DNA',
                    'is_deleted': False,
                    'audit': {
                        'created_on': '2019-01-02',
                        'last_updated_on': '2019-06-02'
                    }
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
        self.assertEqual(project['is_deleted'], False)
        self.assertEqual(project['created_on'], '2019-01-01')
        self.assertEqual(project['last_updated_on'], '2019-06-01')

        project = response.data[1]
        self.assertEqual(project['id'], 'project2')
        self.assertEqual(project['name'], 'Turtle')
        self.assertEqual(project['description'], 'Turtle DNA')
        self.assertEqual(project['is_deleted'], False)
        self.assertEqual(project['created_on'], '2019-01-02')
        self.assertEqual(project['last_updated_on'], '2019-06-02')

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSUtil.get_project_url')
    def test_get_project(self, mock_get_project_url, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'project1',
            'name': 'Mouse',
            'description': 'Mouse RNA',
            'is_deleted': False,
            'audit': {
                'created_on': '2019-01-01',
                'last_updated_on': '2019-06-01'
            }
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
        self.assertEqual(project['is_deleted'], False)
        self.assertEqual(project['created_on'], '2019-01-01')
        self.assertEqual(project['last_updated_on'], '2019-06-01')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_get_project_403_if_no_dds_access(self, mock_dds_util):
        mock_dds_util.return_value.get_project.side_effect = MockDataServiceError(403)
        url = reverse('v2-dukedsproject-list') + 'project1/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_dds_util.return_value.get_project.assert_called_with('project1')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_permissions(self, mock_dds_util):
        permission_response = {
            'results': [
                {
                    'project': {
                        'id': 'project1'
                    },
                    'user': {
                        'id': 'user1'
                    },
                    'auth_role': {
                        'id': 'file_downloader'
                    }
                }
            ]
        }
        mock_dds_util.return_value.get_project_permissions.return_value = permission_response
        url = reverse('v2-dukedsproject-list') + 'project1/permissions/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        project = response.data[0]
        self.assertEqual(project['id'], 'project1_user1')
        self.assertEqual(project['project'], 'project1')
        self.assertEqual(project['user'], 'user1')
        self.assertEqual(project['auth_role'], 'file_downloader')

    @patch('d4s2_api_v2.api.DDSUtil')
    def test_list_permissions_with_user_id_filter(self, mock_dds_util):
        permission_response = {
            'project': {
                'id': 'project1'
            },
            'user': {
                'id': 'user1'
            },
            'auth_role': {
                'id': 'file_downloader'
            }
        }
        mock_dds_util.return_value.get_user_project_permission.return_value = permission_response
        url = reverse('v2-dukedsproject-list') + 'project1/permissions/?user=user1'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data), 1)
        permission = response.data[0]
        self.assertEqual(permission['id'], 'project1_user1')
        self.assertEqual(permission['project'], 'project1')
        self.assertEqual(permission['user'], 'user1')
        self.assertEqual(permission['auth_role'], 'file_downloader')

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSUtil.get_project_url')
    def test_get_summary(self, mock_get_project_url, mock_dds_util):
        mock_project_response = Mock()
        mock_project_response.json.return_value = {
            'id': 'project1',
        }
        mock_children_response = Mock()
        mock_children_response.json.return_value = {
            'results': [
                {'id': 'fo1', 'kind': 'dds-folder', 'parent': { 'kind': 'dds-project'}},
                {'id': 'fi1', 'kind': 'dds-file', 'current_version': {'upload': {'size': 100}}},
                {'id': 'fi2', 'kind': 'dds-file', 'current_version': {'upload': {'size': 200}}},
                {'id': 'fi3', 'kind': 'dds-file', 'current_version': {'upload': {'size': 300}}},
                {'id': 'fo2', 'kind': 'dds-folder', 'parent': { 'kind': 'dds-folder'}},
            ]
        }
        mock_dds_util.return_value.get_project.return_value = mock_project_response
        mock_dds_util.return_value.get_project_children.return_value = mock_children_response
        url = reverse('v2-dukedsproject-list') + 'project1/summary/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summary = response.data
        self.assertEqual(summary['id'], 'project1')
        self.assertEqual(summary['file_count'], 3)
        self.assertEqual(summary['folder_count'], 2)
        self.assertEqual(summary['root_folder_count'], 1)
        self.assertEqual(summary['total_size'], 600)
        self.assertEqual(mock_dds_util.return_value.get_project.call_args, call('project1'))
        self.assertEqual(mock_dds_util.return_value.get_project_children.call_args, call('project1'))

    @patch('d4s2_api_v2.api.DDSProjectSummary.fetch_one')
    def test_get_summary_wraps_error(self, mock_fetch_one):
        mock_fetch_one.side_effect = MockDataServiceError(403)
        url = reverse('v2-dukedsproject-list') + 'project1/summary/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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
    @patch('d4s2_api_v2.api.DDSUtil.get_project_url')
    def test_list_transfers(self, mock_get_project_url, mock_dds_util):
        mock_response = Mock()
        email_template_set = EmailTemplateSet.objects.create(name='someset')
        delivery = DDSDelivery.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                           transfer_id='transfer1', email_template_set=email_template_set)
        mock_response.json.return_value = {
            'results': [
                {
                    'id': 'transfer1',
                    'status': 'pending',
                    'status_comment': 'Some status comment',
                    'audit': {
                        'created_on': '2019-01-01',
                        'last_updated_on': None
                    },
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
                    'audit': {
                        'created_on': '2019-01-01',
                        'last_updated_on': '2019-06-01'
                    },
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
        self.assertEqual(transfer['created_on'], '2019-01-01')
        self.assertEqual(transfer['last_updated_on'], None)

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
        self.assertEqual(transfer['created_on'], '2019-01-01')
        self.assertEqual(transfer['last_updated_on'], '2019-06-01')

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSUtil.get_project_url')
    def test_get_project(self, mock_get_project_url, mock_dds_util):
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'transfer1',
            'status': 'pending',
            'status_comment': 'Some status comment',
            'audit': {
                'created_on': '2019-01-01',
                'last_updated_on': '2019-06-01'
            },
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
        self.assertEqual(transfer['created_on'], '2019-01-01')
        self.assertEqual(transfer['last_updated_on'], '2019-06-01')


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
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')

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
        S3Delivery.objects.create(bucket=bucket, from_user=self.s3_user1, to_user=s3_other_user,
                                  email_template_set=self.email_template_set)

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

        self.user1_email_template_set = EmailTemplateSet.objects.create(name='user1set', storage=StorageTypes.S3)
        UserEmailTemplateSet.objects.create(user=self.normal_user1, email_template_set=self.user1_email_template_set,
                                            storage=StorageTypes.S3)
        self.user2_email_template_set = EmailTemplateSet.objects.create(name='user2set', storage=StorageTypes.S3)
        UserEmailTemplateSet.objects.create(user=self.normal_user2, email_template_set=self.user2_email_template_set,
                                            storage=StorageTypes.S3)
        self.user3_email_template_set = EmailTemplateSet.objects.create(name='user3set', storage=StorageTypes.S3)
        UserEmailTemplateSet.objects.create(user=self.normal_user3, email_template_set=self.user3_email_template_set,
                                            storage=StorageTypes.S3)

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
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2,
                                             email_template_set=self.user1_email_template_set)
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
        S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2,
                                  email_template_set=self.user1_email_template_set)

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
        self.assertEqual(s3_deliveries[0].email_template_set, self.user1_email_template_set)

        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.s3_user2.id,
            'to_user': self.s3_user1.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_delivery_fails_when_user_not_setup(self):
        UserEmailTemplateSet.objects.get(user=self.normal_user1).delete()
        self.login_user1()
        url = reverse('v2-s3delivery-list')
        data = {
            'bucket': self.mouse1_bucket.id,
            'from_user': self.s3_user1.id,
            'to_user': self.s3_user2.id,
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [EMAIL_TEMPLATES_NOT_SETUP_MSG])

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
    @patch('d4s2_api_v2.api.SendDeliveryOperation')
    def test_send_delivery(self, mock_send_delivery_operation,
                           mock_build_accept_url):
        mock_build_accept_url.return_value = 'https://someurl.com'
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2,
                                             email_template_set=self.user1_email_template_set)
        self.login_user1()
        url = reverse('v2-s3delivery-list') + str(delivery.id) + '/send/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_delivery_operation.run.assert_called_with(delivery, 'https://someurl.com')

    def test_send_delivery_with_null_template(self):
        delivery = S3Delivery.objects.create(bucket=self.mouse1_bucket, from_user=self.s3_user1, to_user=self.s3_user2,
                                             email_template_set=None)
        self.login_user1()
        url = reverse('v2-s3delivery-list') + str(delivery.id) + '/send/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [ITEM_EMAIL_TEMPLATES_NOT_SETUP_MSG])


class DeliveryPreviewViewTestCase(APITestCase):

    def setUp(self):
        self.user = django_user.objects.create_user(username='user', password='secret')
        self.client.login(username='user', password='secret')
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user, email_template_set=self.email_template_set)

    def test_cannot_get_list(self):
        url = reverse('v2-delivery_previews')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_get_single(self):
        url = reverse('v2-delivery_previews') + '/some-id/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.DDSMessageFactory')
    def test_create_preview(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'Generated Email Text'

        url = reverse('v2-delivery_previews')
        data = {
            'from_user_id': 'user-1',
            'to_user_id': 'user-2',
            'project_id': 'project-3',
            'transfer_id': '',
            'user_message':'',
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['delivery_email_text'], 'Generated Email Text')
        args, kwargs = mock_message_factory.call_args
        delivery_preview = args[0]
        self.assertEqual(delivery_preview.email_template_set, self.email_template_set)

        # When previewing an email, send() should not be called
        instance.send.assert_not_called()

    @patch('d4s2_api_v2.api.build_accept_url')
    @patch('d4s2_api_v2.api.DDSMessageFactory')
    def test_create_preview_with_transfer_id(self, mock_message_factory, mock_build_accept_url):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'Generated Email Text'
        mock_build_accept_url.return_value = 'https://someurl.com'

        url = reverse('v2-delivery_previews')
        data = {
            'from_user_id': 'user-4',
            'to_user_id': 'user-5',
            'project_id': 'project-6',
            'transfer_id': 'transfer-7',
            'user_message':'',
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['delivery_email_text'], 'Generated Email Text')

        # When previewing an email, send() should not be called
        instance.send.assert_not_called()

        # When providing a transfer_id, this should be passed to build_accept_url
        args, kwargs = mock_build_accept_url.call_args
        self.assertEqual(args[1], 'transfer-7')
        self.assertEqual(args[2], 'dds')

        # Make delivery message should be called with the accept URL
        mock_message_factory.return_value.make_delivery_message.assert_called_with(mock_build_accept_url.return_value)

    def test_cannot_preview_without_auth(self):
        self.client.logout()
        url = reverse('v2-delivery_previews')
        response = self.client.post(url, data={}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('d4s2_api_v2.api.DDSMessageFactory')
    def test_cannot_preview_when_user_not_setup(self, mock_message_factory):
        self.user_email_template_set.delete()
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'Generated Email Text'
        url = reverse('v2-delivery_previews')
        data = {
            'from_user_id': 'user-1',
            'to_user_id': 'user-2',
            'project_id': 'project-3',
            'transfer_id': '',
            'user_message': '',
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [EMAIL_TEMPLATES_NOT_SETUP_MSG])


class DDSAuthProviderViewSetTestCase(AuthenticatedResourceTestCase):
    def setUp(self):
        self.user = django_user.objects.create_user(username='user', password='secret')
        self.client.login(username='user', password='secret')
        self.provider_dict = {
            'id': '123',
            'service_id': '456',
            'name': 'primary',
            'is_deprecated': False,
            'is_default': True,
            'login_initiation_url': 'someurl'
        }

    def test_fails_unauthenticated(self):
        self.client.logout()
        url = reverse('v2-dukedsauthprovider-list')
        response = self.client.post(url, {}, format='json')
        self.assertUnauthorized(response)

    def test_post_not_permitted(self):
        url = reverse('v2-dukedsauthprovider-list')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_permitted(self):
        url = reverse('v2-dukedsauthprovider-list')
        data = {}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAuthProvider')
    def test_get_provider(self, mock_dds_auth_provider, mock_dds_util):
        mock_dds_auth_provider.fetch_list.return_value = [DDSAuthProvider(self.provider_dict)]
        url = reverse('v2-dukedsauthprovider-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        provider = response.data[0]
        self.assertEqual(provider['id'], '123')
        self.assertEqual(provider['is_deprecated'], False)
        self.assertEqual(provider['is_default'], True)

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAuthProvider')
    def test_get_provider(self, mock_dds_auth_provider, mock_dds_util):
        mock_dds_auth_provider.fetch_one.return_value = DDSAuthProvider(self.provider_dict)
        url = reverse('v2-dukedsauthprovider-list') + '123/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        provider = response.data
        self.assertEqual(provider['id'], '123')
        self.assertEqual(provider['is_deprecated'], False)
        self.assertEqual(provider['is_default'], True)
        mock_dds_auth_provider.fetch_one.assert_called_with(mock_dds_util.return_value, '123')


class DDSAuthProviderAffiliatesViewSetTestCase(AuthenticatedResourceTestCase):

    def setUp(self):
        self.user = django_user.objects.create_user(username='user', password='secret')
        self.client.login(username='user', password='secret')
        self.dds_affiliate_dict = {
            'uid': 'joe123',
            'full_name': 'Joe Smith',
            'first_name': 'Joe',
            'last_name': 'Smith',
            'email': 'joe@joe.com',
        }
        self.dds_user_dict = {
            'id': '999',
            'username': 'joe456',
            'full_name': '',
            'first_name': '',
            'last_name': '',
            'email': '',
        }

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAffiliate')
    def test_get_affiliates_uses_default_provider_id(self, mock_dds_affiliate, mock_dds_util):
        mock_dds_affiliate.fetch_list.return_value = [DDSAffiliate(self.dds_affiliate_dict)]
        mock_dds_util.get_openid_auth_provider_id.return_value = '456'
        url = reverse('v2-dukedsauthprovideraffiliates-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        mock_dds_affiliate.fetch_list.assert_called_with(mock_dds_util.return_value, '456', None, None, None)

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAffiliate')
    def test_get_affiliates_by_full_name(self, mock_dds_affiliate, mock_dds_util):
        mock_dds_affiliate.fetch_list.return_value = [DDSAffiliate(self.dds_affiliate_dict)]
        url = reverse('v2-dukedsauthprovideraffiliates-list') + '?auth_provider_id=123&full_name_contains=Joe'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        provider = response.data[0]
        self.assertEqual(provider['uid'], 'joe123')
        mock_dds_affiliate.fetch_list.assert_called_with(mock_dds_util.return_value, '123', 'Joe', None, None)

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAffiliate')
    def test_get_affiliates_by_email(self, mock_dds_affiliate, mock_dds_util):
        mock_dds_affiliate.fetch_list.return_value = [DDSAffiliate(self.dds_affiliate_dict)]
        url = reverse('v2-dukedsauthprovideraffiliates-list') + '?auth_provider_id=123&email=joe@joe.com'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        provider = response.data[0]
        self.assertEqual(provider['uid'], 'joe123')
        mock_dds_affiliate.fetch_list.assert_called_with(mock_dds_util.return_value, '123', None, 'joe@joe.com', None)

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAffiliate')
    def test_get_affiliates_by_username(self, mock_dds_affiliate, mock_dds_util):
        mock_dds_affiliate.fetch_list.return_value = [DDSAffiliate(self.dds_affiliate_dict)]
        url = reverse('v2-dukedsauthprovideraffiliates-list') + '?auth_provider_id=123&username=joe'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        provider = response.data[0]
        self.assertEqual(provider['uid'], 'joe123')
        mock_dds_affiliate.fetch_list.assert_called_with(mock_dds_util.return_value, '123', None, None, 'joe')

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSAffiliate')
    def test_get_single_affiliate_by_username(self, mock_dds_affiliate, mock_dds_util):
        mock_dds_affiliate.fetch_one.return_value = DDSAffiliate(self.dds_affiliate_dict)
        mock_dds_util.get_openid_auth_provider_id.return_value = '456'
        url = reverse('v2-dukedsauthprovideraffiliates-list') + 'joe/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        affiliate = response.data
        self.assertEqual(affiliate['uid'], 'joe123')
        mock_dds_affiliate.fetch_one.assert_called_with(mock_dds_util.return_value, '456', 'joe')

    @patch('d4s2_api_v2.api.DDSUtil')
    @patch('d4s2_api_v2.api.DDSUser')
    def test_get_or_register_user(self, mock_dds_user, mock_dds_util):
        mock_dds_user.get_or_register_user.return_value = DDSUser(self.dds_user_dict)
        mock_dds_util.get_openid_auth_provider_id.return_value = '456'
        url = reverse('v2-dukedsauthprovideraffiliates-list') + 'joe/get-or-register-user/'
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['id'], '999')
        mock_dds_user.get_or_register_user.assert_called_with(mock_dds_util.return_value, '456', 'joe')


class EmailTemplateSetSetup(object):
    def setUp(self):
        self.user = django_user.objects.create_user(username='user', password='secret')
        self.client.login(username='user', password='secret')
        self.core1ts = EmailTemplateSet.objects.create(
            name='core1',
            cc_address='joe@joe.joe',
            reply_address='bob@joe.joe',
            group_name='group1'
        )
        delivery_type = EmailTemplateType.objects.get(name='delivery')
        delivery_type.sequence = 1
        delivery_type.save()
        delivery_type = EmailTemplateType.objects.get(name='accepted_recipient')
        delivery_type.sequence = 2
        delivery_type.save()
        self.core1t2 = EmailTemplate.objects.create(
            template_set=self.core1ts,
            owner=self.user,
            template_type=EmailTemplateType.objects.get(name='accepted_recipient'),
            body="my body",
            subject="some subject",
        )
        self.core1t1 = EmailTemplate.objects.create(
            template_set=self.core1ts,
            owner=self.user,
            template_type=EmailTemplateType.objects.get(name='delivery'),
            body="my body",
            subject="some subject",
        )
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user,
            email_template_set=self.core1ts
        )
        self.core2ts = EmailTemplateSet.objects.create(
            name='core2',
            cc_address='joe@joe.joe',
            reply_address='bob@joe.joe',
            group_name='group2'
        )
        self.core2t1 = EmailTemplate.objects.create(
            template_set=self.core2ts,
            owner=self.user,
            template_type=EmailTemplateType.objects.get(name='delivery'),
            body="my body2",
            subject="some subject2",
        )


class EmailTemplateSetViewSetTestCase(EmailTemplateSetSetup, AuthenticatedResourceTestCase):
    def test_get(self):
        url = reverse('v2-emailtemplatesets-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item['id'], self.core1ts.id)
        self.assertEqual(item['name'], 'core1')
        self.assertEqual(item['cc_address'], 'joe@joe.joe')
        self.assertEqual(item['reply_address'], 'bob@joe.joe')
        self.assertEqual(item['email_templates'], [self.core1t1.id, self.core1t2.id])
        self.assertEqual(item['default'], True)

    @patch('d4s2_api.models.get_users_group_names')
    @patch('d4s2_api.models.current_user_details')
    @patch('d4s2_api.models.get_default_oauth_service')
    def test_get_with_groups(self, mock_get_default_oauth_service, mock_current_user_details,
                             mock_get_users_group_names):
        mock_current_user_details.return_value = {
            'dukeUniqueID': '555666'
        }
        group_manager_connection = GroupManagerConnection.objects.create(account_id='123', password='secret')
        mock_get_users_group_names.return_value = [
            'group2'
        ]
        url = reverse('v2-emailtemplatesets-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        item = response.data[0]
        self.assertEqual(item['id'], self.core1ts.id)
        self.assertEqual(item['name'], 'core1')
        self.assertEqual(item['cc_address'], 'joe@joe.joe')
        self.assertEqual(item['reply_address'], 'bob@joe.joe')
        self.assertEqual(item['email_templates'], [self.core1t1.id, self.core1t2.id])
        self.assertEqual(item['default'], True)
        item = response.data[1]
        self.assertEqual(item['id'], self.core2ts.id)
        self.assertEqual(item['name'], 'core2')
        self.assertEqual(item['cc_address'], 'joe@joe.joe')
        self.assertEqual(item['reply_address'], 'bob@joe.joe')
        self.assertEqual(item['email_templates'], [self.core2t1.id])
        self.assertEqual(item['default'], False)
        mock_get_users_group_names.assert_called_with(group_manager_connection, '555666')


class EmailTemplateViewSetTestCase(EmailTemplateSetSetup, AuthenticatedResourceTestCase):
    def test_get(self):
        url = reverse('v2-emailtemplates-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        item = response.data[0]
        self.assertEqual(item['id'], self.core1t1.id)
        self.assertEqual(item['template_set'], self.core1ts.id)
        self.assertEqual(item['owner'], self.user.id)
        self.assertEqual(item['type'], 'delivery')
        self.assertEqual(item['help_text'], '')
        self.assertEqual(item['body'], 'my body')
        self.assertEqual(item['subject'], 'some subject')
        item = response.data[1]
        self.assertEqual(item['id'], self.core1t2.id)
        self.assertEqual(item['type'], 'accepted_recipient')

    @patch('d4s2_api.models.get_users_group_names')
    @patch('d4s2_api.models.current_user_details')
    @patch('d4s2_api.models.get_default_oauth_service')
    def test_get_with_groups(self, mock_get_default_oauth_service, mock_current_user_details,
                             mock_get_users_group_names):
        mock_current_user_details.return_value = {
            'dukeUniqueID': '555666'
        }
        group_manager_connection = GroupManagerConnection.objects.create(account_id='123', password='secret')
        mock_get_users_group_names.return_value = [
            'group2'
        ]
        url = reverse('v2-emailtemplates-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        item_ids = set([item['id'] for item in response.data])
        self.assertEqual(item_ids, set([self.core1t1.id, self.core1t2.id, self.core2t1.id]))
        mock_get_users_group_names.assert_called_with(group_manager_connection, '555666')


class DukeUserViewSetTestCase(AuthenticatedResourceTestCase):
    @patch('d4s2_api_v2.api.get_users_for_query')
    def test_get_list(self, mock_get_users_for_query):
        mock_get_users_for_query.return_value = [userservice.User({
            'givenName': 'Bob',
            'sn': 'bob',
            'netid': 'bob',
            'display_name': 'Bob Bob',
        })]
        url = reverse('v2-duke-users-list') + "?query=Bob"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], "bob")

    def test_get_fails_without_query(self):
        url = reverse('v2-duke-users-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data[0]), "The 'query' parameter is required.")

    def test_get_fails_with_small_query(self):
        url = reverse('v2-duke-users-list') + "?query=AB"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data[0]), "The query parameter must be at least 3 characters.")

    @patch('d4s2_api_v2.api.get_user_for_netid')
    def test_get_current_user(self, mock_get_user_for_netid):
        mock_get_user_for_netid.return_value = userservice.User({
            'givenName': 'Bob',
            'sn': 'bob',
            'netid': 'bob',
            'display_name': 'Bob Bob',
        })
        url = reverse('v2-duke-users-list') + "current-user/"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], "bob")


class AzDeliveryViewSetTestCase(EmailTemplateSetSetup, AuthenticatedResourceTestCase):
    def setUp(self):
        super().setUp()
        self.user_email_template_set.storage = StorageTypes.AZURE
        self.user_email_template_set.save()
        self.core1ts.storage = StorageTypes.AZURE
        self.core1ts.save()
        self.core2ts.storage = StorageTypes.AZURE
        self.core2ts.save()

    def test_get_list(self):
        other_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/rat",
                container_url="http://127.0.0.1"),
            from_netid="user1",
            to_netid='user2',
            share_user_ids=['user3', 'user4']
        )
        my_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid=self.user.username,
            to_netid='user2',
            share_user_ids=['user3', 'user4']
        )
        to_me_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user2/cat",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4']
        )
        url = reverse('v2-azdeliveries-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        paths = set([item["source_project"]["path"] for item in response.data])
        self.assertEqual(paths, set(["api_user/mouse", 'user2/cat']))

    def test_create_required_fields(self):
        url = reverse('v2-azdeliveries-list')
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('This field is required', str(response.data["source_project"]))
        self.assertIn('This field is required', str(response.data["from_netid"]))
        self.assertIn('This field is required', str(response.data["to_netid"]))

    @patch('d4s2_api_v2.api.get_container_details')
    def test_create(self, mock_get_container_details):
        mock_get_container_details.return_value = {"owner": self.user.username}
        url = reverse('v2-azdeliveries-list')
        response = self.client.post(url, {
            'source_project': {
                'path': 'api_user/mouse',
                'container_url': 'http://127.0.0.1'
            },
            'from_netid': self.user.username,
            'to_netid': 'user2',
            'share_user_ids': ['user3', 'user4']
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['state'], State.NEW)

    @patch('d4s2_api_v2.api.get_container_details')
    def test_create_project_not_found(self, mock_get_container_details):
        mock_get_container_details.return_value = None
        url = reverse('v2-azdeliveries-list')
        container_url = 'http://127.0.0.1'
        response = self.client.post(url, {
            'source_project': {
                'path': 'api_user/mouse',
                'container_url': container_url
            },
            'from_netid': self.user.username,
            'to_netid': 'user2',
            'share_user_ids': ['user3', 'user4']
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data[0]),
                         f'Data Delivery Error: Unable to find project {container_url} in Storage-as-a-Service.')

    @patch('d4s2_api_v2.api.get_container_details')
    def test_create_wrong_user(self, mock_get_container_details):
        mock_get_container_details.return_value = {"owner": "userZ"}
        url = reverse('v2-azdeliveries-list')
        response = self.client.post(url, {
            'source_project': {
                'path': 'api_user/mouse',
                'container_url': 'http://127.0.0.1'
            },
            'from_netid': 'user2',
            'to_netid': self.user.username,
            'share_user_ids': ['user3', 'user4']
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data[0]), 'Data Delivery Error: This project is owned by userZ not you(user).')

    @patch('d4s2_api_v2.api.get_container_details')
    def test_create_project_delivery_already_exists(self, mock_get_container_details):
        mock_get_container_details.return_value = {"owner": self.user.username}
        AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid=self.user.username,
            to_netid='user2',
            share_user_ids=['user3', 'user4']
        )
        url = reverse('v2-azdeliveries-list')
        response = self.client.post(url, {
            'source_project': {
                'path': 'api_user/mouse',
                'container_url': 'http://127.0.0.1'
            },
            'from_netid': self.user.username,
            'to_netid': 'user2',
            'share_user_ids': ['user3', 'user4']
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data[0]), 'Data Delivery Error: An active delivery for this project already exists.')

    def test_put(self):
        delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4']
        )
        url = reverse('v2-azdeliveries-list') + str(delivery.id) + '/'
        data = {
            'user_message': "Sample 3 was not included."
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.user_message, 'Sample 3 was not included.')

    @patch('d4s2_api_v2.api.AzMessageFactory')
    def test_send(self, mock_message_factory):
        mock_message_factory.return_value.make_delivery_message.return_value = Mock(email_text="Email Details")
        az_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4'],
            email_template_set=self.core2ts
        )
        url = reverse('v2-azdeliveries-list') + str(az_delivery.id) + '/send/'
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['delivery_email_text'], 'Email Details')
        mock_message_factory.return_value.make_delivery_message.return_value.send.assert_called_with()
        az_delivery.refresh_from_db()
        self.assertEqual(az_delivery.state, State.NOTIFIED)


    @patch('d4s2_api_v2.api.AzMessageFactory')
    def test_cancel(self, mock_message_factory):
        mock_message_factory.return_value.make_canceled_message.return_value = Mock(email_text="Email Details")
        az_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4'],
            email_template_set=self.core2ts
        )
        url = reverse('v2-azdeliveries-list') + str(az_delivery.id) + '/cancel/'
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, 200)
        mock_message_factory.return_value.make_canceled_message.return_value.send.assert_called_with()
        az_delivery.refresh_from_db()
        self.assertEqual(az_delivery.state, State.CANCELED)

    def test_manifest(self):
        signed_manifest = Signer().sign('{"A":1}')
        az_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4'],
            email_template_set=self.core2ts,
            manifest=AzObjectManifest.objects.create(content=signed_manifest)
        )
        url = reverse('v2-azdeliveries-list') + str(az_delivery.id) + '/manifest/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['manifest'], {'A': 1})
        self.assertEqual(response.data['status'], 'Signature Verified')

    @patch('d4s2_api_v2.api.create_project_summary')
    def test_summary(self, mock_create_project_summary):
        summary = AzureProjectSummary(id='123', based_on='data')
        summary.total_size = 1000
        summary.file_count = 2
        summary.folder_count = 3
        summary.root_folder_count = 1
        summary.error_msg = "Error Details"
        mock_create_project_summary.return_value = summary
        az_delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="api_user/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user2',
            to_netid=self.user.username,
            share_user_ids=['user3', 'user4'],
            email_template_set=self.core2ts
        )
        url = reverse('v2-azdeliveries-list') + str(az_delivery.id) + '/summary/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'id': '123',
            'based_on': 'data',
            'total_size': 1000,
            'file_count': 2,
            'folder_count': 3,
            'root_folder_count': 1,
            'error_msg': 'Error Details'
        })


class AzDeliveryPreviewViewTestCase(APITestCase):

    def setUp(self):
        self.user = django_user.objects.create_user(username='user', password='secret')
        self.client.login(username='user', password='secret')
        self.email_template_set = EmailTemplateSet.objects.create(name='someset', storage=StorageTypes.AZURE)
        self.user_email_template_set = UserEmailTemplateSet.objects.create(
            user=self.user, email_template_set=self.email_template_set,
            storage=StorageTypes.AZURE)

    def test_cannot_get_list(self):
        url = reverse('v2-az-delivery_previews')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_get_single(self):
        url = reverse('v2-az-delivery_previews') + '/some-id/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('d4s2_api_v2.api.AzMessageFactory')
    def test_create_preview(self, mock_message_factory):
        instance = mock_message_factory.return_value.make_delivery_message.return_value
        instance.send = Mock()
        instance.email_text = 'Generated Email Text'

        url = reverse('v2-az-delivery_previews')
        data = {
            'from_netid': 'user1',
            'to_netid': 'user2',
            'transfer_id': 1,
            'user_message': 'Hello',
            'simple_project_name': 'project1',
            'project_url': 'someurl',
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['delivery_email_text'], 'Generated Email Text')
        args, kwargs = mock_message_factory.call_args
        delivery_preview = args[0]
        self.assertEqual(delivery_preview.email_template_set, self.email_template_set)

        # When previewing an email, send() should not be called
        instance.send.assert_not_called()


class AzTransferListViewTestCase(APITestCase):
    def setUp(self):
        self.delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/rat",
                container_url="http://127.0.0.1"),
            destination_project=AzContainerPath.objects.create(
                path="user2/rat",
                container_url="http://127.0.0.2"),
            from_netid="user1",
            to_netid='user2',
            share_user_ids=['user3', 'user4']
        )

    def add_user_to_transfer_poster_group(self):
        self.user = User.objects.create_user(username='user1@sample.com', password='12345')
        login = self.client.login(username='user1@sample.com', password='12345')
        group = Group.objects.create(name='transfer_poster')
        group.user_set.add(self.user)

    def test_post_not_in_group(self):
        url = reverse('v2-az-transfers')
        data = {
            'transfer_uuid': str(uuid.uuid4()),
            'delivery_id': self.delivery.id,
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, 401)

    def test_post_delivery_not_found(self):
        self.add_user_to_transfer_poster_group()
        url = reverse('v2-az-transfers')
        my_uuid = str(uuid.uuid4())
        data = {
            'transfer_uuid': my_uuid,
            'delivery_id': self.delivery.id,
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         f'Unable to find delivery for delivery_id:{self.delivery.id} and transfer_uuid:{my_uuid}')

    def test_post_delivery_wrong_state(self):
        self.add_user_to_transfer_poster_group()
        my_uuid = str(uuid.uuid4())
        self.delivery.transfer_uuid = my_uuid
        self.delivery.save()
        url = reverse('v2-az-transfers')
        data = {
            'transfer_uuid': my_uuid,
            'delivery_id': self.delivery.id,
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, f'Delivery {self.delivery.id} not in TRANSFERRING state.')

    def test_post_error_message(self):
        self.add_user_to_transfer_poster_group()
        my_uuid = str(uuid.uuid4())
        self.delivery.transfer_uuid = my_uuid
        self.delivery.save()
        url = reverse('v2-az-transfers')
        data = {
            'transfer_uuid': my_uuid,
            'delivery_id': self.delivery.id,
            'error_message': 'pipes clogged'
        }
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, State.FAILED)

    @patch('switchboard.azure_util.AzMessageFactory')
    @patch('switchboard.azure_util.settings')
    def test_post_delivery(self, mock_settings, mock_az_message_factory):
        self.add_user_to_transfer_poster_group()
        mock_az_message_factory.return_value.make_processed_message.return_value = Mock(email_text='sometext')
        my_uuid = str(uuid.uuid4())
        self.delivery.transfer_uuid = my_uuid
        self.delivery.state = State.TRANSFERRING
        self.delivery.save()
        url = reverse('v2-az-transfers')
        data = {
            'transfer_uuid': my_uuid,
            'delivery_id': self.delivery.id,
            'manifest': 'something'
        }
        mock_settings.USERNAME_EMAIL_HOST = 'sample.com'
        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, State.ACCEPTED)
        self.assertIn('"files": "something"', self.delivery.manifest.content)
