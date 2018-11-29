from django.test import TestCase
from mock import patch, Mock, MagicMock, call
from switchboard.dds_util import DDSUtil, DeliveryDetails, DeliveryUtil, DDSDeliveryType, \
    SHARE_IN_RESPONSE_TO_DELIVERY_MSG, PROJECT_ADMIN_ID, DDSProject, DDSProjectPermissions, \
    DDS_PERMISSIONS_ID_SEP, MessageDirection, DDSUser, DDSAuthProvider, DDSAffiliate
from d4s2_api.models import User, Share, State, DDSDeliveryShareUser, DDSDelivery, ShareRole, EmailTemplateSet, \
    UserEmailTemplateSet, EmailTemplate, EmailTemplateType
from gcb_web_auth.models import DDSEndpoint


class DDSUtilTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'
        DDSEndpoint.objects.create(api_root='https://api.example.com',
                                   portal_root='https://portal.example.com',
                                   openid_provider_id='openid-123',
                                   openid_provider_service_id='service-456',
                                   is_default=True)

        patcher = patch('switchboard.dds_util.get_dds_token')
        mock_get_dds_token = patcher.start()
        mock_get_dds_token.return_value = MagicMock(key='sometoken')
        self.addCleanup(patcher.stop)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetEmail(self, mockRemoteStore):
        email = 'example@domain.com'
        # Mock a remote user object, and bind it to fetch_user
        remote_user = Mock()
        remote_user.email = email
        instance = mockRemoteStore.return_value
        instance.fetch_user.return_value = remote_user
        ddsutil = DDSUtil(self.user)
        self.assertEqual(email, ddsutil.get_remote_user(self.user_id).email)
        self.assertTrue(instance.fetch_user.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProject(self, mockRemoteStore):
        project_id = '8677-11231-44414-4442'
        project_name = 'Project ABC'
        remote_project = Mock()
        remote_project.name = project_name
        instance = mockRemoteStore.return_value
        instance.fetch_remote_project_by_id.return_value = remote_project
        ddsutil = DDSUtil(self.user)
        self.assertEqual(ddsutil.get_remote_project(project_id).name, project_name)
        self.assertTrue(instance.fetch_remote_project_by_id.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testAddUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        ddsutil = DDSUtil(self.user)
        ddsutil.add_user('userid','projectid','auth_role')
        self.assertTrue(instance.set_user_project_permission.called)

    @patch('switchboard.dds_util.RemoteStore')
    def testRemoveUser(self, mockRemoteStore):
        instance = mockRemoteStore.return_value
        instance.set_user_project_permission = Mock()
        ddsutil = DDSUtil(self.user)
        ddsutil.remove_user('userid','projectid')
        self.assertTrue(instance.revoke_user_project_permission.called)

    def testFailsWithoutUser(self):
        with self.assertRaises(ValueError):
            ddsutil = DDSUtil('')
            ddsutil.remote_store

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProjectTransfer(self, mockRemoteStore):
        mock_requests_response = MagicMock()
        transfer_id = 'abvcca-123'
        get_project_transfer = mockRemoteStore.return_value.data_service.get_project_transfer
        get_project_transfer.return_value = mock_requests_response
        ddsutil = DDSUtil(self.user)
        project_transfer_response = ddsutil.get_project_transfer(transfer_id)
        self.assertTrue(get_project_transfer.called_with(transfer_id))
        self.assertEqual(project_transfer_response, mock_requests_response)

    @patch('switchboard.dds_util.RemoteStore')
    def testGetProjectTransfers(self, mockRemoteStore):
        mock_requests_response = MagicMock()
        mock_data_service = mockRemoteStore.return_value.data_service
        mock_data_service.get_all_project_transfers.return_value = mock_requests_response
        ddsutil = DDSUtil(self.user)
        project_transfers_response = ddsutil.get_project_transfers()
        self.assertTrue(mock_data_service.get_all_project_transfers.called)
        self.assertEqual(project_transfers_response, mock_requests_response)

    def test_get_user_project_permission(self):
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_user_project_permission.return_value.json.return_value = {
            'auth_role': {
                'id': PROJECT_ADMIN_ID
            }
        }
        dds_util._remote_store = mock_remote_store
        resp = dds_util.get_user_project_permission(project_id='123', user_id='456')
        self.assertEqual(resp['auth_role']['id'], PROJECT_ADMIN_ID)
        mock_remote_store.data_service.get_user_project_permission.assert_called_with('123', '456')

    def test_get_project_permissions(self):
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_project_permissions.return_value.json.return_value = {
            'auth_role': {
                'id': PROJECT_ADMIN_ID
            }
        }
        dds_util._remote_store = mock_remote_store
        resp = dds_util.get_project_permissions(project_id='123')
        self.assertEqual(resp['auth_role']['id'], PROJECT_ADMIN_ID)
        mock_remote_store.data_service.get_project_permissions.assert_called_with('123')

    def test_get_project_url(self):
        dds_util = DDSUtil(user=Mock())
        project_url = dds_util.get_project_url('123')
        self.assertEqual(project_url, 'https://portal.example.com/#/project/123')

    def test_cancel_project_transfer(self):
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        dds_util._remote_store = mock_remote_store
        dds_util.cancel_project_transfer(transfer_id='123')

    def test_get_users_no_filter(self):
        mock_user = Mock(name='joe')
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_users.return_value = [mock_user]
        dds_util._remote_store = mock_remote_store
        users = dds_util.get_users()
        self.assertEqual(users, [mock_user])
        mock_remote_store.data_service.get_users.assert_called_with(None, None, None)

    def test_get_users_with_filters(self):
        mock_user = Mock(name='joe')
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_users.return_value = [mock_user]
        dds_util._remote_store = mock_remote_store
        users = dds_util.get_users(full_name_contains='Joe', email='joe@joe.com', username='joe')
        self.assertEqual(users, [mock_user])
        mock_remote_store.data_service.get_users.assert_called_with('Joe', 'joe@joe.com', 'joe')

    def test_get_auth_providers(self):
        mock_provider = Mock(name='provider1')
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_auth_providers.return_value.json.return_value = [mock_provider]
        dds_util._remote_store = mock_remote_store
        providers = dds_util.get_auth_providers()
        self.assertEqual(providers, [mock_provider])
        mock_remote_store.data_service.get_auth_providers.assert_called_with()

    def test_get_auth_provider(self):
        mock_provider = Mock(name='provider1')
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_auth_provider.return_value.json.return_value = mock_provider
        dds_util._remote_store = mock_remote_store
        provider = dds_util.get_auth_provider('provider1')
        self.assertEqual(provider, mock_provider)
        mock_remote_store.data_service.get_auth_provider.assert_called_with('provider1')

    def test_get_auth_provider_affiliates(self):
        mock_affiliate = Mock(id='affiliate1')
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.get_auth_provider_affiliates.return_value.json.return_value = [mock_affiliate]
        dds_util._remote_store = mock_remote_store
        affiliates = dds_util.get_auth_provider_affiliates(auth_provider_id='provider1', full_name_contains='Joe')
        self.assertEqual(affiliates, [mock_affiliate])
        mock_remote_store.data_service.get_auth_provider_affiliates.assert_called_with('provider1', 'Joe')

    def test_auth_provider_add_user(self):
        mock_dds_user = Mock()
        dds_util = DDSUtil(user=Mock())
        mock_remote_store = Mock()
        mock_remote_store.data_service.auth_provider_add_user.return_value.json.return_value = mock_dds_user
        dds_util._remote_store = mock_remote_store
        dds_user = dds_util.auth_provider_add_user(auth_provider_id='provider1', username='user1')
        self.assertEqual(dds_user, mock_dds_user)
        mock_remote_store.data_service.auth_provider_add_user.assert_called_with('provider1', 'user1')


class TestDeliveryDetails(TestCase):
    @patch('switchboard.dds_util.DDSUtil')
    @patch('switchboard.dds_util.DDSUser')
    @patch('switchboard.dds_util.DDSProjectTransfer')
    def test_get_email_context(self, mock_dds_project_transfer, mock_dds_user, mock_dds_util):
        mock_dds_project_transfer.fetch_one.return_value.project_dict = {
            'name': 'SomeProject'
        }
        mock_dds_user.fetch_one.side_effect = [
            Mock(full_name='joe', email='joe@joe.com'),
            Mock(full_name='bob', email='bob@bob.com'),
        ]
        mock_dds_util.return_value.get_project_url.return_value = 'projecturl'
        delivery = Mock(user_message='user message text')
        user = Mock()
        details = DeliveryDetails(delivery, user)
        context = details.get_email_context('accepturl', 'accepted', 'test', warning_message='warning!!')
        self.assertEqual(context['service_name'], 'Duke Data Service')
        self.assertEqual(context['project_name'], 'SomeProject')
        self.assertEqual(context['recipient_name'], 'bob')
        self.assertEqual(context['recipient_email'], 'bob@bob.com')
        self.assertEqual(context['sender_email'], 'joe@joe.com')
        self.assertEqual(context['sender_name'], 'joe')
        self.assertEqual(context['project_url'], 'projecturl')
        self.assertEqual(context['accept_url'], 'accepturl')
        self.assertEqual(context['type'], 'accepted')
        self.assertEqual(context['message'], 'test')
        self.assertEqual(context['user_message'], 'user message text')
        self.assertEqual(context['warning_message'], 'warning!!')

    @patch('switchboard.dds_util.DDSUtil')
    @patch('switchboard.dds_util.DDSUser')
    @patch('switchboard.dds_util.DDSProjectTransfer')
    def test_get_context(self, mock_dds_project_transfer, mock_dds_user, mock_dds_util):
        mock_dds_project_transfer.fetch_one.return_value.project_dict = {
            'name': 'SomeProject',
        }
        mock_dds_user.fetch_one.side_effect = [
            Mock(full_name='joe', email='joe@joe.com'),
            Mock(full_name='bob', email='bob@bob.com'),
        ]
        mock_dds_util.return_value.get_project_url.return_value = 'projecturl'
        delivery = Mock(user_message='user message text', transfer_id='123')
        user = Mock()
        details = DeliveryDetails(delivery, user)
        context = details.get_context()
        self.assertEqual(context['service_name'], 'Duke Data Service')
        self.assertEqual(context['transfer_id'], '123')
        self.assertEqual(context['from_name'], 'joe')
        self.assertEqual(context['from_email'], 'joe@joe.com')
        self.assertEqual(context['to_name'], 'bob')
        self.assertEqual(context['to_email'], 'bob@bob.com')
        self.assertEqual(context['project_title'], 'SomeProject')
        self.assertEqual(context['project_url'], 'projecturl')

    @patch('switchboard.dds_util.DDSProjectTransfer')
    @patch('switchboard.dds_util.DDSProject')
    def test_get_project_from_share(self, mock_dds_project, mock_dds_project_transfer):
        email_template_set = EmailTemplateSet.objects.create(name='someset')
        share = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2',
                                     email_template_set=email_template_set)
        user = Mock()
        mock_project = Mock()
        mock_dds_project.fetch_one.return_value = mock_project

        details = DeliveryDetails(share, user)
        project = details.get_project()
        self.assertEqual(project, mock_project)
        mock_dds_project_transfer.fetch_one.assert_not_called()
        mock_dds_project.fetch_one.assert_called_with(details.ddsutil, 'project1')

    @patch('switchboard.dds_util.DDSProjectTransfer')
    @patch('switchboard.dds_util.DDSProject')
    def test_get_project_from_delivery(self, mock_dds_project, mock_dds_project_transfer):
        email_template_set = EmailTemplateSet.objects.create(name='someset')
        delivery = DDSDelivery.objects.create(project_id='project1',
                                              from_user_id='user1',
                                              to_user_id='user2',
                                              transfer_id='transfer1',
                                              email_template_set=email_template_set)
        user = Mock()
        mock_transfer = Mock()
        mock_dds_project_transfer.fetch_one.return_value = mock_transfer

        details = DeliveryDetails(delivery, user)
        project = details.get_project()
        self.assertEqual(project, mock_dds_project.return_value)
        mock_dds_project_transfer.fetch_one.assert_called_with(details.ddsutil, 'transfer1')
        mock_dds_project.assert_called_with(mock_transfer.project_dict)
        mock_dds_project.fetch_one.assert_not_called()


class DeliveryUtilTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_user')
        self.email_template_set = EmailTemplateSet.objects.create(name='someset')
        UserEmailTemplateSet.objects.create(user=self.user, email_template_set=self.email_template_set)
        file_downloader_type = EmailTemplateType.objects.get(name='share_file_downloader')
        EmailTemplate.objects.create(template_set=self.email_template_set,
                                     template_type=file_downloader_type,
                                     owner=self.user,
                                     subject='sharesubject',
                                     body='sharebody'
                                     )
        self.delivery = DDSDelivery.objects.create(from_user_id='abc123', to_user_id='def456', project_id='ghi789',
                                                   email_template_set=self.email_template_set)
        DDSDeliveryShareUser.objects.create(dds_id='jkl888', delivery=self.delivery)
        DDSDeliveryShareUser.objects.create(dds_id='mno999', delivery=self.delivery)

    @patch('switchboard.dds_util.DDSUtil')
    def test_accept_project_transfer(self, mock_ddsutil):
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.accept_project_transfer()
        mock_ddsutil.return_value.accept_project_transfer.assert_called_with(self.delivery.transfer_id)

    @patch('switchboard.dds_util.DDSUtil')
    @patch('switchboard.dds_util.DeliveryDetails')
    def test_decline_delivery(self, mock_delivery_details, MockDDSUtil):
        mock_ddsutil = MockDDSUtil()
        mock_ddsutil.decline_project_transfer = Mock()
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.decline_delivery('reason')
        MockDDSUtil.assert_any_call(self.user)
        mock_ddsutil.decline_project_transfer.assert_called_with(self.delivery.transfer_id, 'reason')

    @patch('switchboard.dds_util.DDSUtil')
    def test_share_with_additional_users(self, mock_ddsutil):
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.share_with_additional_users()

        # each additional user should have permissions given
        mock_ddsutil.return_value.share_project_with_user.assert_has_calls([
            call('ghi789', 'jkl888', 'file_downloader'),
            call('ghi789', 'mno999', 'file_downloader'),
        ])

        # each additional user should have an email sent (share record)
        share1 = Share.objects.get(to_user_id='jkl888')
        self.assertEqual('ghi789', share1.project_id)
        self.assertEqual(self.delivery.to_user_id, share1.from_user_id)
        self.assertEqual(State.NOTIFIED, share1.state)
        share2 = Share.objects.get(to_user_id='mno999')
        self.assertEqual('ghi789', share2.project_id)
        self.assertEqual(self.delivery.to_user_id, share2.from_user_id)
        self.assertEqual(State.NOTIFIED, share2.state)

    def test_get_warning_message(self):
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        self.assertEqual(delivery_util.get_warning_message(), '')

        delivery_util.failed_share_users.append('joe')
        delivery_util.failed_share_users.append('bob')
        self.assertEqual(delivery_util.get_warning_message(), 'Failed to share with the following user(s): joe, bob')

    @patch('switchboard.dds_util.DDSUtil')
    def test_give_sender_permission(self, mock_dds_util):
        delivery_util = DeliveryUtil(self.delivery, self.user, 'file_downloader', 'Share in response to delivery.')
        delivery_util.give_sender_permission()
        mock_dds_util.return_value.share_project_with_user.assert_called_with(
            'ghi789', 'abc123', ShareRole.DOWNLOAD)


class DDSDeliveryTypeTestCase(TestCase):

    def setUp(self):
        self.delivery_type = DDSDeliveryType()

    def test_name_and_delivery_cls(self):
        self.assertEqual(self.delivery_type.name, 'dds')
        self.assertEqual(self.delivery_type.delivery_cls, DDSDelivery)

    @patch('switchboard.dds_util.DeliveryDetails')
    def test_makes_dds_delivery_details(self, mock_delivery_details):
        details = self.delivery_type.make_delivery_details('arg1','arg2')
        mock_delivery_details.assert_called_once_with('arg1', 'arg2')
        self.assertEqual(details, mock_delivery_details.return_value)

    @patch('switchboard.dds_util.DeliveryUtil')
    def test_makes_dds_delivery_util(self, mock_delivery_util):
        util = self.delivery_type.make_delivery_util('arg1','arg2')
        mock_delivery_util.assert_called_once_with('arg1', 'arg2',
                                                   share_role=ShareRole.DOWNLOAD,
                                                   share_user_message=SHARE_IN_RESPONSE_TO_DELIVERY_MSG)
        self.assertEqual(util, mock_delivery_util.return_value)

    @patch('switchboard.dds_util.DDSUtil')
    @patch('switchboard.dds_util.DDSMessageFactory')
    @patch('switchboard.dds_util.Share')
    def test_transfer_delivery(self, mock_share, mock_dds_message_factory, mock_dds_util):
        share_users = Mock()
        share_users.all.return_value = [Mock(dds_id='shareuser1'), Mock(dds_id='shareuser2')]
        mock_delivery = Mock(share_users=share_users)
        mock_user = Mock()
        mock_dds_message_factory.return_value.make_processed_message.side_effect = [
            Mock(email_text='first_email_content'),
            Mock(email_text='second_email_content')
        ]

        warning_message = self.delivery_type.transfer_delivery(mock_delivery, mock_user)

        self.assertEqual(warning_message, '')
        mock_dds_util.return_value.accept_project_transfer.assert_called_with(mock_delivery.transfer_id)
        mock_dds_util.return_value.share_project_with_user.assert_has_calls([
            call(mock_delivery.project_id, 'shareuser1', 'file_downloader'),
            call(mock_delivery.project_id, 'shareuser2', 'file_downloader'),
            call(mock_delivery.project_id, mock_delivery.from_user_id, 'file_downloader'),
        ])

        make_processed_message = mock_dds_message_factory.return_value.make_processed_message
        make_processed_message.assert_has_calls([
            call('accepted', MessageDirection.ToSender, warning_message=''),
            call('accepted_recipient', MessageDirection.ToRecipient),
        ])
        mock_delivery.mark_accepted.assert_called_with(
            mock_user.get_username.return_value,
            'first_email_content',
            'second_email_content'
        )


class DDSProjectTestCase(TestCase):
    def test_constructor(self):
        project = DDSProject({
            'id': '123',
            'name': 'mouse',
            'description': 'mouse rna analysis',
            'is_deleted': False,
        })
        self.assertEqual(project.id, '123')
        self.assertEqual(project.name, 'mouse')
        self.assertEqual(project.description, 'mouse rna analysis')
        self.assertEqual(project.is_deleted, False)

    def test_fetch_list(self):
        mock_dds_util = Mock()
        mock_dds_util.get_projects.return_value.json.return_value = {
            'results': [
                {
                    'id': '123',
                    'name': 'mouse',
                    'description': 'mouse RNA',
                    'is_deleted': False,
                }
            ]
        }
        projects = DDSProject.fetch_list(mock_dds_util)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, '123')
        self.assertEqual(projects[0].name, 'mouse')
        self.assertEqual(projects[0].description, 'mouse RNA')
        self.assertEqual(projects[0].is_deleted, False)


class DDSProjectPermissionsTestCase(TestCase):
    def test_constructor(self):
        permissions = DDSProjectPermissions(project_permission_dict={
            'project': {
                'id': 'project1'
            },
            'user': {
                'id': 'user1'
            },
            'auth_role': {
                'id': 'file_downloader'
            }
        })
        self.assertEqual(permissions.id, 'project1{}user1'.format(DDS_PERMISSIONS_ID_SEP))
        self.assertEqual(permissions.project, 'project1')
        self.assertEqual(permissions.user, 'user1')
        self.assertEqual(permissions.auth_role, 'file_downloader')

    def test_fetch_one(self):
        mock_dds_util = Mock()
        mock_dds_util.get_user_project_permission.return_value = {
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
        permissions = DDSProjectPermissions.fetch_one(mock_dds_util, project_id='project1', user_id='user1')
        self.assertEqual(permissions.id, 'project1{}user1'.format(DDS_PERMISSIONS_ID_SEP))
        self.assertEqual(permissions.project, 'project1')
        self.assertEqual(permissions.user, 'user1')
        self.assertEqual(permissions.auth_role, 'file_downloader')

    def test_fetch_list_without_user_id(self):
        mock_dds_util = Mock()
        mock_dds_util.get_project_permissions.return_value = {
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
        ary = DDSProjectPermissions.fetch_list(mock_dds_util, project_id='project1')
        self.assertEqual(len(ary), 1)
        permissions = ary[0]
        self.assertEqual(permissions.id, 'project1{}user1'.format(DDS_PERMISSIONS_ID_SEP))
        self.assertEqual(permissions.project, 'project1')
        self.assertEqual(permissions.user, 'user1')
        self.assertEqual(permissions.auth_role, 'file_downloader')

    def test_fetch_list_with_user_id(self):
        mock_dds_util = Mock()
        mock_dds_util.get_user_project_permission.return_value = {
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
        ary = DDSProjectPermissions.fetch_list(mock_dds_util, project_id='project1', user_id='user1')
        self.assertEqual(len(ary), 1)
        permissions = ary[0]
        self.assertEqual(permissions.id, 'project1{}user1'.format(DDS_PERMISSIONS_ID_SEP))
        self.assertEqual(permissions.project, 'project1')
        self.assertEqual(permissions.user, 'user1')
        self.assertEqual(permissions.auth_role, 'file_downloader')


class DDSUserTestCase(TestCase):
    def test_get_or_register_user_when_user_exists(self):
        mock_user = Mock()
        mock_dds_util = Mock()
        mock_dds_util.get_users.return_value = [mock_user]
        dds_user = DDSUser.get_or_register_user(mock_dds_util, auth_provider_id='provider1', username='joe1')
        self.assertEqual(dds_user, mock_user)
        mock_dds_util.get_users.assert_called_with(username='joe1')
        mock_dds_util.auth_provider_add_user.assert_not_called()

    def test_get_or_register_user_when_user_not_found(self):
        mock_dds_util = Mock()
        mock_dds_util.get_users.return_value = []
        mock_dds_util.auth_provider_add_user.return_value = {
            'id': 'joe1',
            'username': 'joe1',
            'full_name': '',
            'first_name': '',
            'last_name': '',
            'email': ''
        }
        dds_user = DDSUser.get_or_register_user(mock_dds_util, auth_provider_id='provider1', username='joe1')
        self.assertEqual(dds_user.username, 'joe1')
        mock_dds_util.get_users.assert_called_with(username='joe1')
        mock_dds_util.auth_provider_add_user.assert_called_with('provider1', 'joe1')


class DDSAuthProviderTestCase(TestCase):
    def setUp(self):
        self.provider_dict = {
            'id': '123',
            'service_id': '456',
            'name': 'primary',
            'is_deprecated': False,
            'is_default': True,
            'login_initiation_url': 'someurl'
        }
        self.mock_dds_util = Mock()

    def test_constructor(self):
        provider = DDSAuthProvider(self.provider_dict)
        self.assertEqual(provider.id, '123')
        self.assertEqual(provider.service_id, '456')
        self.assertEqual(provider.name, 'primary')
        self.assertEqual(provider.is_deprecated, False)
        self.assertEqual(provider.is_default, True)
        self.assertEqual(provider.login_initiation_url, 'someurl')

    def test_fetch_list(self):
        self.mock_dds_util.get_auth_providers.return_value = {'results': [self.provider_dict]}
        providers = DDSAuthProvider.fetch_list(self.mock_dds_util)
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].id, '123')

    def test_fetch_one(self):
        self.mock_dds_util.get_auth_provider.return_value = self.provider_dict
        provider = DDSAuthProvider.fetch_one(self.mock_dds_util, dds_provider_id='123')
        self.assertEqual(provider.id, '123')
        self.mock_dds_util.get_auth_provider.assert_called_with('123')

    @staticmethod
    def fetch_list(dds_util):
        response = dds_util.get_auth_providers()
        return DDSAuthProvider.from_list(response['results'])

    @staticmethod
    def fetch_one(dds_util, dds_user_id):
        response = dds_util.get_auth_provider(dds_user_id)
        return DDSAuthProvider(response)


class DDSAffiliateTestCase(TestCase):
    def setUp(self):
        self.dds_affiliate_dict = {
            'uid': 'joe123',
            'full_name': 'Joe Smith',
            'first_name': 'Joe',
            'last_name': 'Smith',
            'email': 'joe@joe.com',
        }
        self.mock_dds_util = Mock()

    def test_constructor(self):
        affiliate = DDSAffiliate(self.dds_affiliate_dict)
        self.assertEqual(affiliate.uid, 'joe123')
        self.assertEqual(affiliate.full_name, 'Joe Smith')
        self.assertEqual(affiliate.first_name, 'Joe')
        self.assertEqual(affiliate.last_name, 'Smith')
        self.assertEqual(affiliate.email, 'joe@joe.com')

    def test_fetch_list(self):
        self.mock_dds_util.get_auth_provider_affiliates.return_value = {
            'results': [
                self.dds_affiliate_dict
            ]
        }
        affiliates = DDSAffiliate.fetch_list(self.mock_dds_util, 'provider1', 'Joe')
        self.assertEqual(len(affiliates), 1)
        self.assertEqual(affiliates[0].uid, 'joe123')
        self.assertEqual(affiliates[0].full_name, 'Joe Smith')
        self.mock_dds_util.get_auth_provider_affiliates.assert_called_with('provider1', 'Joe')
