from django.test import TestCase
from background_task.tasks import tasks
import uuid
from mock import patch, ANY, Mock, call
from switchboard.azure_util import get_details_from_container_url, make_acl, AzDeliveryDetails, AzDeliveryType, \
    AzDelivery, State, TransferFunctions, AzureTransfer, \
    User, settings, AzDeliveryError, AzNotRecipientException, \
    AzureProjectSummary, decompose_dfs_url, get_container_details
from d4s2_api.utils import MessageDirection
from d4s2_api.models import AzTransferStates, AzContainerPath
from django.conf import settings
import requests.exceptions

class TestFuncs(TestCase):
    def setUp(self):
        self.container_url = "https://my_storage_acct.blob.core.windows.net/my_container"

    def test_get_details_from_container_url(self):
        container_url = self.container_url
        storage_account, fs_name = get_details_from_container_url(container_url)
        self.assertEqual(storage_account, 'my_storage_acct')
        self.assertEqual(fs_name, 'my_container')  # Azure refers to buckets as both containers and file_systems

    def test_make_acl(self):
        user_id = '123'
        acl = make_acl(user_id, permissions='r-x')
        self.assertEqual(acl, 'user:123:r-x,default:user:123:r-x')


class TestAzDeliveryDetails(TestCase):
    def setUp(self):
        self.delivery = Mock(from_netid='user1', to_netid='user2', transfer_id='123', user_message='UserMsg')
        self.delivery.get_simple_project_name.return_value = "mouse"
        self.delivery.make_project_url.return_value = "someurl"
        self.user = Mock()
        self.details = AzDeliveryDetails(self.delivery, self.user)

    @patch('switchboard.azure_util.get_user_for_netid')
    def test_get_from_user(self, mock_get_user_for_netid):
        self.assertEqual(self.details.get_from_user(), mock_get_user_for_netid.return_value)
        mock_get_user_for_netid.assert_called_with('user1')

    @patch('switchboard.azure_util.get_user_for_netid')
    def test_get_to_user(self, mock_get_user_for_netid):
        self.assertEqual(self.details.get_to_user(), mock_get_user_for_netid.return_value)
        mock_get_user_for_netid.assert_called_with('user2')

    @patch('switchboard.azure_util.get_user_for_netid')
    def test_get_context(self, mock_get_user_for_netid):
        mock_get_user_for_netid.side_effect = [
            Mock(username='user1', full_name='User1', email='user1@sample.com'),
            Mock(username='user2', full_name='User2', email='user2@sample.com'),
        ]
        context = self.details.get_context()

        self.assertEqual(context, {
            'from_email': 'user1@sample.com',
            'from_name': 'User1',
            'from_netid': 'user1',
            'project_title': 'mouse',
            'project_url': 'someurl',
            'service_name': 'Azure Blob Storage',
            'to_email': 'user2@sample.com',
            'to_name': 'User2',
            'to_netid': 'user2',
            'transfer_id': '123'
        })

    @patch('switchboard.azure_util.get_user_for_netid')
    def test_get_email_context(self, mock_get_user_for_netid):
        mock_get_user_for_netid.side_effect = [
            Mock(username='user1', full_name='User1', email='user1@sample.com'),
            Mock(username='user2', full_name='User2', email='user2@sample.com'),
        ]
        context = self.details.get_email_context(accept_url='otherurl', process_type='delivery', reason='somereason',
                                                 warning_message='warningmsg')
        self.maxDiff = None
        self.assertEqual(context, {
            'accept_url': 'otherurl',
            'message': 'somereason',
            'project_name': 'mouse',
            'project_url': 'someurl',
            'recipient_email': 'user2@sample.com',
            'recipient_name': 'User2',
            'recipient_netid': 'user2',
            'sender_email': 'user1@sample.com',
            'sender_name': 'User1',
            'sender_netid': 'user1',
            'service_name': 'Azure Blob Storage',
            'type': 'delivery',
            'user_message': 'UserMsg',
            'warning_message': 'warningmsg'
        })

    def test_decline_delivery(self):
        self.details.decline_delivery(reason="Some Reason")


class TestAzDeliveryType(TestCase):
    def test_props(self):
        self.assertEqual(AzDeliveryType.name, 'azure')
        self.assertEqual(AzDeliveryType.delivery_cls, AzDelivery)
        self.assertEqual(AzDeliveryType.transfer_in_background, True)

    @patch('switchboard.azure_util.AzDelivery')
    def test_get_delivery(self, mock_azure_delivery):
        self.assertEqual(AzDeliveryType.get_delivery(transfer_id='123'),
                         mock_azure_delivery.objects.get.return_value)
        mock_azure_delivery.objects.get.assert_called_with(pk='123')

    @patch('switchboard.azure_util.settings')
    def test_make_delivery_details(self, mock_settings):
        mock_settings.USERNAME_EMAIL_HOST = 'sample.com'
        AzDeliveryType.make_delivery_details(delivery=Mock(to_netid='joe'),
                                             user=Mock(username='joe@sample.com'))

    @patch('switchboard.azure_util.settings')
    def test_make_delivery_details_wrong_user(self, mock_settings):
        mock_settings.USERNAME_EMAIL_HOST = 'sample.com'
        with self.assertRaises(AzNotRecipientException):
            AzDeliveryType.make_delivery_details(delivery=Mock(to_netid='bob'),
                                                 user=Mock(username='joe@sample.com'))

    @patch('switchboard.azure_util.settings')
    def test_make_delivery_util(self, mock_settings):
        mock_settings.USERNAME_EMAIL_HOST = 'sample.com'
        AzDeliveryType.make_delivery_util(delivery=Mock(to_netid='joe'), user=Mock(username='joe@sample.com'))

    @patch('switchboard.azure_util.settings')
    def test_make_delivery_util_wrong_user(self, mock_settings):
        mock_settings.USERNAME_EMAIL_HOST = 'sample.com'
        with self.assertRaises(AzNotRecipientException):
            AzDeliveryType.make_delivery_util(delivery=Mock(to_netid='joe'), user=Mock(username='bob@sample.com'))

    @patch('switchboard.azure_util.TransferFunctions')
    def test_transfer_delivery(self, mock_transfer_functions):
        delivery = Mock(to_netid='user2', source_project=Mock(container_url='someurl'))
        delivery.id = '123'
        delivery.get_simple_project_name.return_value = "mouse"
        AzDeliveryType.transfer_delivery(delivery, Mock(username='user2@sample.com'))
        mock_transfer_functions.transfer_delivery.assert_called_with('123')

    @patch('switchboard.azure_util.TransferFunctions')
    def test_transfer_delivery_wrong_user(self, mock_transfer_functions):
        delivery = Mock(to_netid='user2', source_project=Mock(container_url='someurl'))
        delivery.id = '123'
        delivery.get_simple_project_name.return_value = "mouse"
        delivery.destination_project = None
        with self.assertRaises(AzNotRecipientException):
            AzDeliveryType.transfer_delivery(delivery, Mock(username='user1@sample.com'))

    @patch('switchboard.azure_util.AzMessageFactory')
    def test_make_processed_message(self, mock_message_factory):
        AzDeliveryType.make_processed_message(delivery=Mock(), user=Mock(), process_type='deliver',
                                              direction=MessageDirection.ToSender, warning_message='warning')
        mock_message_factory.return_value.make_processed_message.assert_called_with(
            'deliver', MessageDirection.ToSender, warning_message='warning'
        )


class TestTransferFunctions(TestCase):
    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123')
        tasks.run_next_task()
        expected_calls = [
            call.ensure_transferring_state(),
            call.record_object_manifest(),
            call.transfer_project(),
            call.give_download_users_permissions(),
            call.update_owner_permissions(),
            call.email_sender(),
            call.email_recipient(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123')
        tasks.run_next_task()
        expected_calls = [
            call.ensure_transferring_state(),
            call.notify_transfer_service(),
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)


class TestAzureTransfer(TestCase):
    def setUp(self):
        self.delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/mouse",
                container_url="https://fromacct.blob.core.windows.net/fromcontainer"),
            from_netid='user1',
            destination_project=AzContainerPath.objects.create(
                path="user2/mouse",
                container_url="https://toacct.blob.core.windows.net/tocontainer"
            ),
            to_netid='user2',
            share_user_ids=['user3', 'user4'],
        )
        self.transfer = AzureTransfer(delivery_id=self.delivery.id)
        self.transfer.source_project = Mock(container_url="http://127.0.0.1", path='user1/mouse')
        self.transfer.destination_project = Mock(container_url="http://127.0.0.1", path='user2/mouse')
        self.transfer.azure_users = Mock()
        User.objects.create_user(username="{}@{}".format(self.delivery.from_netid, settings.USERNAME_EMAIL_HOST))

    def test_ensure_transferring_state(self):
        self.transfer.ensure_transferring_state()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, State.TRANSFERRING)

    @patch('switchboard.azure_util.print')
    def test_record_object_manifest(self, mock_print):
        files_manifest = [{"name": "file1.txt"}]
        self.transfer.record_object_manifest(files_manifest)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.CREATED_MANIFEST)
        self.assertIn('[{"name": "file1.txt"}]', self.delivery.manifest.content)
        mock_print.assert_called_with('Recorded object manifest for {}.'.format(self.delivery.id))

    @patch('switchboard.azure_util.print')
    @patch('switchboard.azure_util.AzMessageFactory')
    def test_email_sender(self, mock_message_factory, mock_print):
        mock_message_factory.return_value.make_processed_message.return_value = Mock(email_text="email1")
        self.transfer.email_sender()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.sender_completion_email_text, "email1")
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.EMAILED_SENDER)
        mock_message_factory.return_value.make_processed_message.return_value.send.assert_called_with()
        mock_print.assert_called_with('Notifying sender delivery {} has been accepted.'.format(self.delivery.id))

    @patch('switchboard.azure_util.print')
    @patch('switchboard.azure_util.AzMessageFactory')
    def test_email_recipient(self, mock_message_factory, mock_print):
        mock_message_factory.return_value.make_processed_message.return_value = Mock(email_text="email2")
        self.transfer.email_recipient()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.EMAILED_RECIPIENT)
        self.assertEqual(self.delivery.recipient_completion_email_text, "email2")
        mock_message_factory.return_value.make_processed_message.return_value.send.assert_called_with()
        mock_print.assert_called_with('Notifying receiver transfer of delivery {} is complete.'.format(self.delivery.id))

    @patch('switchboard.azure_util.print')
    def test_mark_complete(self, mock_print):
        self.transfer.mark_complete()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.COMPLETE)
        self.assertEqual(self.delivery.state, State.ACCEPTED)
        mock_print.assert_called_with("Marking delivery {} complete.".format(self.delivery.id))

    def test_set_failed_and_record_exception(self):
        self.transfer.set_failed_and_record_exception(ValueError("Oops"))
        error = AzDeliveryError.objects.first()
        self.assertEqual(error.delivery.id, self.delivery.id)
        self.assertEqual(error.message, "Oops")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, State.FAILED)

    @patch('switchboard.azure_util.requests')
    @patch('switchboard.azure_util.uuid')
    @patch('switchboard.azure_util.settings')
    def test_notify_transfer_service(self, mock_settings, mock_uuid, mock_requests):
        mock_settings.TRANSFER_PIPELINE_URL = 'https://sample.com'
        my_uuid = uuid.uuid4()
        mock_uuid.uuid4.return_value = my_uuid
        self.transfer.notify_transfer_service()
        mock_requests.post.assert_called_with(
            'https://sample.com',
            headers={'user-agent': 'duke-data-delivery/2.0.0'},
            json={
                'Source_StorageAccount': 'fromacct',
                'Source_FileSystem': 'fromcontainer',
                'Source_TopLevelFolder': 'user1/mouse',
                'Sink_StorageAccount': 'toacct',
                'Sink_FileSystem': 'tocontainer',
                'Sink_TopLevelFolder': 'user2/mouse',
                'Webhook_DeliveryID': self.transfer.delivery.id,
                'Webhook_TransferUUID': str(my_uuid)
            }
        )
        self.assertEqual(self.transfer.delivery.transfer_uuid, str(my_uuid))


class TestAzureProjectSummary(TestCase):
    def test_apply_path_dict(self):
        summary = AzureProjectSummary(id='1', based_on='somelocation')
        self.assertEqual(summary.total_size, 0)
        self.assertEqual(summary.file_count, 0)
        self.assertEqual(summary.folder_count, 0)
        self.assertEqual(summary.root_folder_count, 0)
        self.assertEqual(summary.sub_folder_count, 0)
        summary.apply_path_dict({
            "is_directory": True,
            "name": "netid/projectname/top.txt"
        })
        self.assertEqual(summary.total_size, 0)
        self.assertEqual(summary.file_count, 0)
        self.assertEqual(summary.folder_count, 1)
        self.assertEqual(summary.root_folder_count, 1)
        self.assertEqual(summary.sub_folder_count, 0)
        summary.apply_path_dict({
            "is_directory": True,
            "name": "netid/projectname/data/subdir.txt"
        })
        self.assertEqual(summary.total_size, 0)
        self.assertEqual(summary.file_count, 0)
        self.assertEqual(summary.folder_count, 2)
        self.assertEqual(summary.root_folder_count, 1)
        self.assertEqual(summary.sub_folder_count, 1)
        summary.apply_path_dict({
            "is_directory": False,
            "content_length": 1000
        })
        self.assertEqual(summary.total_size, 1000)
        self.assertEqual(summary.file_count, 1)
        self.assertEqual(summary.folder_count, 2)
        self.assertEqual(summary.root_folder_count, 1)
        self.assertEqual(summary.sub_folder_count, 1)


class TestGlobalFunctions(TestCase):
    def test_decompose_dfs_url(self):
        acct, container = decompose_dfs_url("https://myacct.dfs.core.windows.net/my-container")
        self.assertEqual(acct, 'myacct')
        self.assertEqual(container, 'my-container')

    @patch('switchboard.azure_util.requests')
    @patch('switchboard.azure_util.settings')
    def test_get_container_details(self, mock_settings, mock_requests):
        mock_settings.AZURE_SAAS_KEY = 'mykey'
        mock_settings.AZURE_SAAS_URL = 'myurl'
        response = Mock()
        response.json.return_value = { "result": "ok"}
        mock_requests.get.return_value = response
        details = get_container_details("https://myacct.dfs.core.windows.net/my-container")
        self.assertEqual(details, {"result": "ok"})
        mock_requests.get.assert_called_with('myurl/api/FileSystems/myacct/my-container',
                                             headers={'Saas-FileSystems-Api-Key': 'mykey'},
                                             timeout=1)

    @patch('switchboard.azure_util.requests')
    @patch('switchboard.azure_util.settings')
    def test_get_container_details_retry_once(self, mock_settings, mock_requests):
        mock_settings.AZURE_SAAS_KEY = 'mykey'
        mock_settings.AZURE_SAAS_URL = 'myurl'
        response = Mock()
        response.json.return_value = { "result": "ok"}
        mock_requests.get.side_effect = [requests.exceptions.ReadTimeout(), response]
        details = get_container_details("https://myacct.dfs.core.windows.net/my-container")
        self.assertEqual(details, {"result": "ok"})
        mock_requests.get.assert_called_with('myurl/api/FileSystems/myacct/my-container',
                                             headers={'Saas-FileSystems-Api-Key': 'mykey'},
                                             timeout=1)
