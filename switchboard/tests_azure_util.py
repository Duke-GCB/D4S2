from django.test import TestCase
from mock import patch, ANY, Mock, call
from switchboard.azure_util import get_details_from_container_url, make_acl, project_exists, AzDataLakeProject, \
    AzUsers, AzDeliveryDetails, AzDeliveryType, AzDelivery, AzContainerPath, State, TransferFunctions, AzureTransfer, \
    User, settings, AzDeliveryError, AzStorageConfig, AzNotRecipientException, AzDestinationProjectAlreadyExists
from d4s2_api.utils import MessageDirection
from d4s2_api.models import AzTransferStates
from django.conf import settings


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

    @patch('switchboard.azure_util.AzDataLakeProject')
    def test_project_exists(self, mock_az_project):
        result = project_exists(self.container_url, 'user1/mouse')
        self.assertEqual(result, mock_az_project.return_value.exists.return_value)
        mock_az_project.assert_called_with(self.container_url, 'user1/mouse')


class TestAzDataLakeProject(TestCase):
    def setUp(self):
        AzStorageConfig.objects.create(
            name='my_storage_acct',
            subscription_id='subid',
            resource_group='rg1',
            storage_account='my_storage_acct',
            container_name='my_container',
            storage_account_key='sa_key'
        )
        AzStorageConfig.objects.create(
            name='my_storage_acct',
            subscription_id='subid',
            resource_group='rg1',
            storage_account='my_storage_acct',
            container_name='other_container',
            storage_account_key='sa_key2'
        )
        self.container_url = "https://my_storage_acct.blob.core.windows.net/my_container"
        self.other_container_url = "https://my_storage_acct.blob.core.windows.net/other_container"
        self.project = AzDataLakeProject(container_url=self.container_url, path="user1/mouse")
        self.project.service = Mock()
        self.project.directory_client = Mock()


    def test_exists(self):
        self.assertEqual(self.project.exists(), self.project.directory_client.exists.return_value)

    def test_ensure_parent_directory(self):
        self.project.service.get_directory_client.return_value.exists.return_value = False
        self.project.ensure_parent_directory()
        self.project.service.get_directory_client.return_value.create_directory.assert_called_with()

    def test_move_same_container(self):
        self.project.move(destination_container_url=self.container_url, destination_path="user2/mouse")
        self.project.directory_client.rename_directory.assert_called_with('my_container/user2/mouse')

    @patch('switchboard.azure_util.subprocess')
    def test_move_different_container(self, mock_subprocess):
        self.project.move(destination_container_url=self.other_container_url, destination_path="user2/mouse")
        mock_subprocess.run.assert_called_with(
            ['azcopy', 'copy', '--recursive',
             'https://my_storage_acct.blob.core.windows.net/my_container/user1/mouse',
             'https://my_storage_acct.blob.core.windows.net/other_container/user2/mouse'],
            check=True)
        self.project.directory_client.delete_directory.assert_called_with()

    def test_get_file_manifest(self):
        fsc = self.project.service.get_file_system_client.return_value
        mock_dir = Mock()
        mock_dir.is_directory = True
        mock_file = Mock()
        mock_file.is_directory = False
        fsc.get_paths.return_value = [
            mock_dir,
            mock_file
        ]
        fc = fsc.get_file_client.return_value
        fc.get_file_properties.return_value = {
            'lease': 'SomeValue',
            'content_settings': {
                "content_type": "text/plain",
                "content_md5": b"ABC"
            }
        }
        manifest = self.project.get_file_manifest()
        self.assertEqual(manifest, [
            {
                'content_settings': {
                    'content_type': 'text/plain',
                    'content_md5': '414243'
                }
            }
        ])

    def test_add_download_user(self):
        self.project.add_download_user(azure_user_id="123")
        fsc = self.project.service.get_file_system_client.return_value
        dc = fsc.get_directory_client.return_value
        dc.update_access_control_recursive.assert_called_with(acl='user:123:r-x,default:user:123:r-x')

    def test_set_owner(self):
        fsc = self.project.service.get_file_system_client.return_value
        mock_file = Mock()
        mock_file.name = 'user1/mouse/file1.txt'
        fsc.get_paths.return_value = [mock_file]
        self.project.set_owner(azure_user_id="123")
        fsc.get_file_client.assert_has_calls([
            call('user1/mouse'),
            call().set_access_control(owner='123'),
            call('user1/mouse/file1.txt'),
            call().set_access_control(owner='123'),
        ])


class TestAzUsers(TestCase):
    @patch('switchboard.azure_util.GraphClient')
    def test_get_azure_user_id(self, mock_graph_client):
        mock_response = Mock()
        mock_response.json.return_value = {"id": "789"}
        mock_graph_client.return_value.get.return_value = mock_response
        users = AzUsers(credential=None)
        result = users.get_azure_user_id(netid='user1')
        self.assertEqual(result, "789")


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
    @patch('switchboard.azure_util.project_exists')
    def test_transfer_delivery(self, mock_project_exists, mock_transfer_functions):
        mock_project_exists.return_value = False
        delivery = Mock(to_netid='user2', source_project=Mock(container_url='someurl'))
        delivery.id = '123'
        delivery.get_simple_project_name.return_value = "mouse"
        delivery.destination_project = None
        AzDeliveryType.transfer_delivery(delivery, Mock(username='user2@sample.com'))
        self.assertEqual(delivery.destination_project.path, 'user2/mouse')
        self.assertEqual(delivery.destination_project.container_url, 'someurl')
        mock_transfer_functions.transfer_delivery.assert_called_with('123')

    @patch('switchboard.azure_util.TransferFunctions')
    @patch('switchboard.azure_util.project_exists')
    def test_transfer_delivery_destinaton_exists(self, mock_project_exists, mock_transfer_functions):
        mock_project_exists.return_value = True
        delivery = Mock(to_netid='user2', source_project=Mock(container_url='someurl'))
        delivery.id = '123'
        delivery.get_simple_project_name.return_value = "mouse"
        delivery.destination_project = None
        with self.assertRaises(AzDestinationProjectAlreadyExists):
            AzDeliveryType.transfer_delivery(delivery, Mock(username='user2@sample.com'))

    @patch('switchboard.azure_util.TransferFunctions')
    @patch('switchboard.azure_util.project_exists')
    def test_transfer_delivery_wrong_user(self, mock_project_exists, mock_transfer_functions):
        mock_project_exists.return_value = True
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
    def test_transfer_delivery_no_transfer(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123', transfer_project=False)
        expected_calls = [
            call.ensure_transferring_state(),
            call.give_download_users_permissions(),
            call.update_owner_permissions(),
            call.email_sender(),
            call.email_recipient(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery_no_add_users(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123', transfer_project=False, add_download_users=False)
        expected_calls = [
            call.ensure_transferring_state(),
            call.update_owner_permissions(),
            call.email_sender(),
            call.email_recipient(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery_no_change_owner(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123', transfer_project=False, add_download_users=False,
                                            change_owner=False)
        expected_calls = [
            call.ensure_transferring_state(),
            call.email_sender(),
            call.email_recipient(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery_no_sender(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123', transfer_project=False, add_download_users=False,
                                            change_owner=False, email_sender=False)
        expected_calls = [
            call.ensure_transferring_state(),
            call.email_recipient(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.AzureTransfer')
    def test_transfer_delivery_no_recipient(self, mock_azure_transfer):
        mock_azure_transfer.return_value.email_sender.return_value.email_text = "emailtext1"
        mock_azure_transfer.return_value.email_recipient.return_value.email_text = "emailtext2"
        TransferFunctions.transfer_delivery(delivery_id='123', transfer_project=False, add_download_users=False,
                                            change_owner=False, email_sender=False, email_recipient=False)
        expected_calls = [
            call.ensure_transferring_state(),
            call.mark_complete()
        ]
        mock_azure_transfer.return_value.assert_has_calls(expected_calls)

    @patch('switchboard.azure_util.TransferFunctions.transfer_delivery')
    @patch('switchboard.azure_util.print')
    def test_restart_transfer_bad_state(self, mock_print, mock_transfer_delivery):
        delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user1',
            destination_project=AzContainerPath.objects.create(
                path="user2/mouse",
                container_url="http://127.0.0.1"
            ),
            to_netid='user2',
            share_user_ids=['user3', 'user4'],
        )
        TransferFunctions.restart_transfer(delivery.id)
        mock_print.assert_called_with('Delivery {} is not in transferring state.'.format(delivery.id))

    @patch('switchboard.azure_util.TransferFunctions.transfer_delivery')
    @patch('switchboard.azure_util.print')
    def test_restart_transfer_bad_state(self, mock_print, mock_transfer_delivery):
        delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user1',
            destination_project=AzContainerPath.objects.create(
                path="user2/mouse",
                container_url="http://127.0.0.1"
            ),
            to_netid='user2',
            share_user_ids=['user3', 'user4'],
            state=State.TRANSFERRING,
        )
        state_to_expected_params = [
            # transfer state       transfer_project, add_download_users, change_owner
            (AzTransferStates.NEW, True, True, True, True, True),
            (AzTransferStates.CREATED_MANIFEST, True, True, True, True, True),
            (AzTransferStates.TRANSFERRED_PROJECT, False, True, True, True, True),
            (AzTransferStates.ADDED_DOWNLOAD_USERS, False, False, True, True, True),
            (AzTransferStates.CHANGED_OWNER, False, False, False, True, True),
            (AzTransferStates.EMAILED_SENDER, False, False, False, False, True),
            (AzTransferStates.EMAILED_RECIPIENT, False, False, False, False, False)
        ]
        for transfer_state, transfer_project, add_download_users, change_owner, email_sender, email_recipient in\
                state_to_expected_params:
            delivery.transfer_state = transfer_state
            delivery.save()
            mock_transfer_delivery.reset()
            TransferFunctions.restart_transfer(delivery.id)
            mock_transfer_delivery.assert_called_with(
                delivery.id,
                transfer_project=transfer_project,
                add_download_users=add_download_users,
                change_owner=change_owner,
                email_sender=email_sender,
                email_recipient=email_recipient)


class TestAzureTransfer(TestCase):
    @patch('switchboard.azure_util.AzDataLakeProject')
    def setUp(self, _):
        self.delivery = AzDelivery.objects.create(
            source_project=AzContainerPath.objects.create(
                path="user1/mouse",
                container_url="http://127.0.0.1"),
            from_netid='user1',
            destination_project=AzContainerPath.objects.create(
                path="user2/mouse",
                container_url="http://127.0.0.1"
            ),
            to_netid='user2',
            share_user_ids=['user3', 'user4'],
        )
        self.transfer = AzureTransfer(delivery_id=self.delivery.id, credential=Mock())
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
        self.transfer.source_project.get_file_manifest.return_value = [{"name": "file1.txt"}]
        self.transfer.record_object_manifest()
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.CREATED_MANIFEST)
        self.assertIn('[{"name": "file1.txt"}]', self.delivery.manifest.content)
        mock_print.assert_called_with('Recorded object manifest for user1/mouse.')

    @patch('switchboard.azure_util.print')
    def test_transfer_project(self, mock_print):
        self.transfer.transfer_project()
        self.transfer.source_project.move.assert_called_with('http://127.0.0.1', 'user2/mouse')
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.TRANSFERRED_PROJECT)
        mock_print.assert_has_calls([
            call('Beginning project transfer for user1/mouse to user2/mouse.'),
            call('Project transfer complete for user1/mouse to user2/mouse.')
        ])

    @patch('switchboard.azure_util.print')
    def test_give_download_users_permissions(self, mock_print):
        self.transfer.azure_users.get_azure_user_id.side_effect = ["111", "333", "444"]
        self.transfer.give_download_users_permissions()
        self.transfer.azure_users.get_azure_user_id.assert_has_calls([
            call('user1'),
            call('user3'),
            call('user4')
        ])
        self.transfer.destination_project.add_download_user.assert_has_calls([
            call("111"), call("333"), call("444")
        ])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.ADDED_DOWNLOAD_USERS)


    @patch('switchboard.azure_util.print')
    def test_update_owner_permissions(self, mock_print):
        self.transfer.azure_users.get_azure_user_id.return_value = "222"
        self.transfer.update_owner_permissions()
        self.transfer.azure_users.get_azure_user_id.assert_called_with("user2")
        self.transfer.destination_project.set_owner.assert_called_with("222")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.CHANGED_OWNER)

    @patch('switchboard.azure_util.print')
    def test_update_owner_permissions(self, mock_print):
        self.transfer.azure_users.get_azure_user_id.return_value = "222"
        self.transfer.update_owner_permissions()
        self.transfer.azure_users.get_azure_user_id.assert_called_with("user2")
        self.transfer.destination_project.set_owner.assert_called_with("222")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.transfer_state, AzTransferStates.CHANGED_OWNER)
        mock_print.assert_called_with('Updating owner permissions for {}.'.format(self.delivery.id))

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
