from django.test import TestCase
from mock import patch, Mock, MagicMock, call
from switchboard.dds_util import DDSUtil, DeliveryDetails, DeliveryUtil, DDSDeliveryType, \
    SHARE_IN_RESPONSE_TO_DELIVERY_MSG, PROJECT_ADMIN_ID, DDSProject, ProjectDeliverableStatus
from d4s2_api.models import User, Share, State, DDSDeliveryShareUser, DDSDelivery, ShareRole
from gcb_web_auth.models import DDSEndpoint


class DDSUtilTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='ddsutil_user')
        self.user_id = 'abcd-1234-efgh-8876'
        DDSEndpoint.objects.create(api_root='', portal_root='', openid_provider_id='')

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


class TestDeliveryDetails(TestCase):

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_share_template(self, MockEmailTemplate):
        MockEmailTemplate.for_share = Mock(return_value=MagicMock(subject='share subject', body='share body'))
        delivery = Mock()
        user = Mock()
        details = DeliveryDetails(delivery, user)
        subject, body = details.get_share_template_text()
        self.assertTrue(MockEmailTemplate.for_share.called_with(delivery))
        self.assertEqual(subject, 'share subject')
        self.assertEqual(body, 'share body')

    @patch('switchboard.dds_util.EmailTemplate')
    def test_gets_action_template(self, MockEmailTemplate):
        MockEmailTemplate.for_user = Mock(return_value=MagicMock(subject='action subject', body='action body'))
        delivery = Mock()
        user = Mock()
        details = DeliveryDetails(delivery, user)
        subject, body = details.get_action_template_text('accepted')
        self.assertEqual(subject, 'action subject')
        self.assertEqual(body, 'action body')
        self.assertTrue(MockEmailTemplate.for_operation.called_with(delivery, 'accepted'))

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
        share = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2')
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
        delivery = DDSDelivery.objects.create(project_id='project1',
                                              from_user_id='user1',
                                              to_user_id='user2',
                                              transfer_id='transfer1')
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
        self.delivery = DDSDelivery.objects.create(from_user_id='abc123', to_user_id='def456', project_id='ghi789')
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
    @patch('switchboard.dds_util.DeliveryDetails')
    def test_share_with_additional_users(self, mock_delivery_details, mock_ddsutil):
        mock_delivery_details.return_value.get_share_template_text.return_value = 'subject', 'template body'
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


class DDSProjectTestCase(TestCase):
    def test_constructor(self):
        project = DDSProject({
            'id': '123',
            'name': 'mouse',
            'description': 'mouse rna analysis',
            'is_deliverable': True,
        })
        self.assertEqual(project.id, '123')
        self.assertEqual(project.name, 'mouse')
        self.assertEqual(project.description, 'mouse rna analysis')
        self.assertEqual(project.is_deliverable, True)

    @patch('switchboard.dds_util.ProjectDeliverableStatus')
    def test_fetch_list(self, mock_project_deliverable_status):
        mock_dds_util = Mock()
        mock_dds_util.get_projects.return_value.json.return_value = {
            'results': [
                {
                    'id': '123',
                    'name': 'mouse',
                    'description': 'mouse RNA',
                }
            ]
        }
        mock_project_deliverable_status.return_value.calculate.return_value = True
        projects = DDSProject.fetch_list(mock_dds_util, is_deliverable=None)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, '123')
        self.assertEqual(projects[0].name, 'mouse')
        self.assertEqual(projects[0].description, 'mouse RNA')
        self.assertEqual(projects[0].is_deliverable, True)

    @patch('switchboard.dds_util.ProjectDeliverableStatus')
    def test_fetch_list_not_deliverable(self, mock_project_deliverable_status):
        mock_dds_util = Mock()
        mock_dds_util.get_projects.return_value.json.return_value = {
            'results': [
                {
                    'id': '123',
                    'name': 'mouse',
                    'description': 'mouse RNA',
                }
            ]
        }
        mock_project_deliverable_status.return_value.calculate.return_value = False
        projects = DDSProject.fetch_list(mock_dds_util, is_deliverable=None)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, '123')
        self.assertEqual(projects[0].is_deliverable, False)

    @patch('switchboard.dds_util.ProjectDeliverableStatus')
    def test_fetch_list_filtering(self, mock_project_deliverable_status):
        mock_dds_util = Mock()
        mock_dds_util.get_projects.return_value.json.return_value = {
            'results': [
                {
                    'id': '123',
                    'name': 'mouse',
                    'description': 'mouse RNA',
                },
                {
                    'id': '456',
                    'name': 'rat',
                    'description': 'rat RNA',
                },
            ]
        }
        mock_project_deliverable_status.return_value.calculate.side_effect = [True, False]
        projects = DDSProject.fetch_list(mock_dds_util, is_deliverable=True)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, '123')
        self.assertEqual(projects[0].name, 'mouse')
        self.assertEqual(projects[0].description, 'mouse RNA')
        self.assertEqual(projects[0].is_deliverable, True)


class ProjectDeliverableStatusTestCase(TestCase):
    def setUp(self):
        self.mock_dds_util = Mock()
        self.mock_current_user = Mock()
        self.mock_current_user.id = '456'
        self.mock_dds_util.get_current_user.return_value = self.mock_current_user

    def test_calculate_with_admin_priv(self):
        self.mock_dds_util.get_user_project_permission.return_value = {
            'auth_role': {
                'id': PROJECT_ADMIN_ID
            }
        }
        status = ProjectDeliverableStatus(self.mock_dds_util)
        project_dict = {
            'id': '123',
            'is_deleted': False,
        }
        self.assertEqual(status.calculate(project_dict), True)

    def test_calculate_without_admin_priv(self):
        self.mock_dds_util.get_user_project_permission.return_value = {
            'auth_role': {
                'id': 'other'
            }
        }
        status = ProjectDeliverableStatus(self.mock_dds_util)
        project_dict = {
            'id': '123',
            'is_deleted': False,
        }
        self.assertEqual(status.calculate(project_dict), False)

    def test_calculate_when_project_deleted(self):
        status = ProjectDeliverableStatus(self.mock_dds_util)
        project_dict = {
            'id': '123',
            'is_deleted': True,
        }
        self.assertEqual(status.calculate(project_dict), False)
