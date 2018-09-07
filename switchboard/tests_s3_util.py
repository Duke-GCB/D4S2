from django.test import TestCase
from mock import patch, Mock, call
from d4s2_api.models import S3Bucket, S3User, S3UserTypes, S3Delivery, User, S3Endpoint, State
from switchboard.s3_util import S3Resource, S3DeliveryUtil, S3DeliveryDetails, S3BucketUtil, \
    S3NoSuchBucket, S3DeliveryType, S3TransferOperation, S3DeliveryError, SendDeliveryBackgroundFunctions, \
    SendDeliveryOperation, S3NotRecipientException, MessageDirection


class S3DeliveryTestBase(TestCase):
    def setUp(self):
        self.user_agent = User.objects.create(username='agent',
                                              email='agent@agent.com',
                                              first_name='Agent',
                                              last_name='007')
        self.from_user = User.objects.create(username='from_user',
                                             email='from_user@from_user.com',
                                             first_name='From',
                                             last_name='User')
        self.to_user = User.objects.create(username='to_user',
                                           email='to_user@to_user.com',
                                           first_name='To',
                                           last_name='User')
        self.endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        self.s3_agent_user = S3User.objects.create(endpoint=self.endpoint,
                                                   s3_id='agent_s3_id',
                                                   user=self.user_agent,
                                                   type=S3UserTypes.AGENT)
        self.s3_from_user = S3User.objects.create(endpoint=self.endpoint,
                                                  s3_id='from_user_s3_id',
                                                  user=self.from_user,
                                                  type=S3UserTypes.NORMAL)
        self.s3_to_user = S3User.objects.create(endpoint=self.endpoint,
                                                s3_id='to_user_s3_id',
                                                user=self.to_user,
                                                type=S3UserTypes.NORMAL)
        self.s3_bucket = S3Bucket.objects.create(name='mouse',
                                                 owner=self.s3_from_user,
                                                 endpoint=self.endpoint)
        self.s3_delivery = S3Delivery.objects.create(bucket=self.s3_bucket,
                                                     from_user=self.s3_from_user,
                                                     to_user=self.s3_to_user,
                                                     user_message='user message')


class S3DeliveryUtilTestCase(S3DeliveryTestBase):
    def test_s3_agent_property(self):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        s3_agent = s3_delivery_util.s3_agent
        self.assertEqual(s3_agent.type, S3UserTypes.AGENT)
        self.assertEqual(s3_agent.id, self.s3_agent_user.id)

    def test_destination_bucket_name_property(self):
        self.s3_bucket.name = 'mouse'
        self.s3_bucket.save()
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        destination_bucket_name = s3_delivery_util.destination_bucket_name
        self.assertEqual(destination_bucket_name, 'delivery_mouse')

        self.s3_bucket.name = 'ThisBucket'
        self.s3_bucket.save()
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        destination_bucket_name = s3_delivery_util.destination_bucket_name
        self.assertEqual(destination_bucket_name, 'delivery_ThisBucket')

    @patch('switchboard.s3_util.S3Resource')
    def test_give_agent_permissions(self, mock_s3_resource):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        s3_delivery_util.give_agent_permissions()
        mock_s3_resource.return_value.grant_bucket_acl.assert_called_with(
            'mouse',
            grant_full_control_user=s3_delivery_util.s3_agent
        )

    @patch('switchboard.s3_util.S3Resource')
    def test_accept_project_transfer(self, mock_s3_resource):
        mock_s3_grant_read = Mock()
        mock_s3_copy_files = Mock()
        mock_s3_cleanup_bucket = Mock()
        mock_s3_resource.side_effect = [
            mock_s3_grant_read,
            mock_s3_copy_files,
            mock_s3_cleanup_bucket
        ]

        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        s3_delivery_util.accept_project_transfer()

        # First we grant read permissions to to_user while retaining control for agent user
        mock_s3_grant_read.grant_bucket_acl.assert_called_with(
            'mouse',
            grant_full_control_user=self.s3_agent_user,
            grant_read_user=self.s3_to_user
        )
        mock_s3_grant_read.grant_objects_acl.assert_called_with(
            'mouse',
            grant_full_control_user=self.s3_agent_user,
            grant_read_user=self.s3_to_user
        )

        # As the to user create a bucket and copy the files
        mock_s3_copy_files.create_bucket.assert_called_with(s3_delivery_util.destination_bucket_name)
        mock_s3_copy_files.copy_bucket.assert_called_with(s3_delivery_util.source_bucket_name,
                                                          s3_delivery_util.destination_bucket_name)

        # As the agent Delete the source (this also deletes the files)
        mock_s3_cleanup_bucket.delete_bucket.assert_called_with(s3_delivery_util.source_bucket_name)

    @patch('switchboard.s3_util.S3Resource')
    def test_decline_delivery(self, mock_s3_resource):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery)
        s3_delivery_util.decline_delivery('test reason')
        mock_s3_resource.return_value.grant_bucket_acl.assert_called_with(
            'mouse', grant_full_control_user=self.s3_from_user
        )


class S3DeliveryDetailsTestCase(S3DeliveryTestBase):
    def test_simple_getters(self):
        s3_delivery_details = S3DeliveryDetails(self.s3_delivery, self.from_user)
        self.assertEqual(s3_delivery_details.get_from_user(), self.from_user)
        self.assertEqual(s3_delivery_details.get_to_user(), self.to_user)

    def test_get_context(self):
        s3_delivery_details = S3DeliveryDetails(self.s3_delivery, self.from_user)
        context = s3_delivery_details.get_context()
        expected_context = {
            'to_email': 'to_user@to_user.com',
            'from_name': 'From User',
            'project_title': 'mouse',
            'project_url': 's3://mouse',
            'service_name': 'S3',
            'from_email': 'from_user@from_user.com',
            'to_name': 'To User',
            'transfer_id': str(self.s3_delivery.transfer_id)
        }
        self.assertEqual(context, expected_context)

    def test_get_email_context(self):
        s3_delivery_details = S3DeliveryDetails(self.s3_delivery, self.from_user)
        context = s3_delivery_details.get_email_context(
            accept_url='accepturl',
            process_type='accept',
            reason='somereason',
            warning_message='oops'
        )
        expected_context = {
            'accept_url': 'accepturl',
            'message': 'somereason',
            'project_name': 'mouse',
            'project_url': 's3://mouse',
            'service_name': 'S3',
            'recipient_email': 'to_user@to_user.com',
            'recipient_name': 'To User',
            'sender_email': 'from_user@from_user.com',
            'sender_name': 'From User',
            'type': 'accept',
            'user_message': 'user message',
            'warning_message': 'oops'
        }
        self.assertEqual(context, expected_context)

    @patch('switchboard.s3_util.EmailTemplate')
    def test_get_action_template_text(self, mock_email_template):
        mock_email_template.for_user.return_value = Mock(subject='email subject', body='email body')

        s3_delivery_details = S3DeliveryDetails(self.s3_delivery, self.from_user)
        subject, body = s3_delivery_details.get_action_template_text(action_name='accept')

        self.assertEqual(subject, 'email subject')
        self.assertEqual(body, 'email body')

        mock_email_template.for_user.return_value = None
        with self.assertRaises(RuntimeError):
            s3_delivery_details.get_action_template_text(action_name='accept')


class S3ResourceTestCase(TestCase):
    def setUp(self):
        self.s3_user = Mock(
            s3_id='SomeID',
            credential=Mock(aws_secret_access_key='secret'),
            endpoint=Mock(url='someurl')
        )

    @patch('switchboard.s3_util.boto3')
    def test_create_bucket(self, mock_boto3):
        s3_resource = S3Resource(self.s3_user)
        s3_resource.create_bucket(bucket_name='somebucket')

        mock_bucket_constructor = mock_boto3.session.Session.return_value.resource.return_value.Bucket
        mock_bucket_constructor.assert_called_with('somebucket')
        self.assertEqual(mock_bucket_constructor.return_value.create.called, True)

    @patch('switchboard.s3_util.boto3')
    def test_copy_bucket(self, mock_boto3):
        mock_source_bucket = Mock()
        mock_source_bucket.objects.all.return_value = [
            Mock(key='key1'),
            Mock(key='key2')
        ]
        mock_bucket_constructor = mock_boto3.session.Session.return_value.resource.return_value.Bucket
        mock_bucket_constructor.return_value = mock_source_bucket

        s3_resource = S3Resource(self.s3_user)
        s3_resource.copy_bucket(source_bucket_name='from_bucket', destination_bucket_name='to_bucket')

        mock_bucket_constructor.assert_called_with('from_bucket')
        s3_resource.s3.meta.client.copy_object.assert_has_calls([
            call(Bucket='to_bucket',
                 CopySource={'Bucket': 'from_bucket', 'Key': 'key1'},
                 Key='key1',
                 MetadataDirective='COPY'),
            call(Bucket='to_bucket',
                 CopySource={'Bucket': 'from_bucket', 'Key': 'key2'},
                 Key='key2',
                 MetadataDirective='COPY')
        ])

    @patch('switchboard.s3_util.boto3')
    def test_delete_bucket(self, mock_boto3):
        mock_bucket = Mock()
        mock_file1 = Mock(key='key1')
        mock_file2 = Mock(key='key2')
        mock_bucket.objects.all.return_value = [
            mock_file1,
            mock_file2
        ]
        mock_bucket_constructor = mock_boto3.session.Session.return_value.resource.return_value.Bucket
        mock_bucket_constructor.return_value = mock_bucket

        s3_resource = S3Resource(self.s3_user)
        s3_resource.delete_bucket(bucket_name='somebucket')

        mock_bucket_constructor.assert_called_with('somebucket')
        self.assertEqual(mock_bucket_constructor.return_value.delete.called, True)
        self.assertEqual(mock_file1.delete.called, True)
        self.assertEqual(mock_file2.delete.called, True)

    @patch('switchboard.s3_util.boto3')
    def test_grant_bucket_acl(self, mock_boto3):
        s3_resource = S3Resource(self.s3_user)
        s3_resource.grant_bucket_acl(
            bucket_name='somebucket',
            grant_full_control_user=Mock(s3_id='user1'),
            grant_read_user=Mock(s3_id='user2'),
        )

        mock_bucket_acl_constructor = mock_boto3.session.Session.return_value.resource.return_value.BucketAcl
        mock_bucket_acl_constructor.return_value.put.assert_called_with(
            GrantFullControl='id=user1',
            GrantRead='id=user2')

    @patch('switchboard.s3_util.boto3')
    def test_grant_objects_acl(self, mock_boto3):
        mock_bucket = Mock()
        mock_file1 = Mock(key='key1')
        mock_file2 = Mock(key='key2')
        mock_bucket.objects.all.return_value = [
            mock_file1,
            mock_file2
        ]
        mock_bucket_constructor = mock_boto3.session.Session.return_value.resource.return_value.Bucket
        mock_bucket_constructor.return_value = mock_bucket

        s3_resource = S3Resource(self.s3_user)
        s3_resource.grant_objects_acl(
            bucket_name='somebucket',
            grant_full_control_user=Mock(s3_id='user3'),
            grant_read_user=Mock(s3_id='user4'),
        )

        mock_object_acl_constructor = mock_boto3.session.Session.return_value.resource.return_value.ObjectAcl
        mock_object_acl_constructor.return_value.put.assert_called_with(
            GrantFullControl='id=user3',
            GrantRead='id=user4')

    @patch('switchboard.s3_util.boto3')
    def test_get_bucket_owner(self, mock_boto3):
        bucket1 = Mock()
        bucket1.name = 'bucket1'
        bucket2 = Mock()
        bucket2.name = 'bucket2'
        bucket3 = Mock()
        bucket3.name = 'bucket3'
        mock_s3 = mock_boto3.session.Session.return_value.resource.return_value
        mock_s3.BucketAcl.return_value.owner = {'ID': self.s3_user.s3_id}
        s3_resource = S3Resource(self.s3_user)
        self.assertEqual(s3_resource.get_bucket_owner('somebucket'), self.s3_user.s3_id)
        mock_s3.BucketAcl.assert_called_with('somebucket')

    @patch('switchboard.s3_util.boto3')
    def test_get_objects_for_bucket(self, mock_boto3):
        mock_s3 = mock_boto3.session.Session.return_value.resource.return_value
        s3_resource = S3Resource(self.s3_user)
        mock_object_summary1 = Mock()
        mock_object_summary1.Object.return_value = '<s3_object1>'
        mock_object_summary2 = Mock()
        mock_object_summary2.Object.return_value = '<s3_object2>'
        mock_s3.Bucket.return_value.objects.all.return_value = [mock_object_summary1, mock_object_summary2]
        s3_objects = s3_resource.get_objects_for_bucket(bucket_name='somebucket')
        self.assertEqual(s3_objects, ['<s3_object1>', '<s3_object2>'])


class S3BucketUtilTestCase(S3DeliveryTestBase):
    @patch('switchboard.s3_util.S3Resource')
    def test_user_owns_bucket(self, mock_s3_resource):
        mock_s3_resource.return_value.get_bucket_owner.side_effect = [
            self.s3_to_user.s3_id,
            self.s3_from_user.s3_id,
            self.s3_to_user.s3_id,
        ]

        s3_bucket_util = S3BucketUtil(self.endpoint, self.to_user)
        self.assertEqual(s3_bucket_util.user_owns_bucket(bucket_name='test1'), True)
        self.assertEqual(s3_bucket_util.user_owns_bucket(bucket_name='test1'), False)
        self.assertEqual(s3_bucket_util.user_owns_bucket(bucket_name='test1'), True)

    @patch('switchboard.s3_util.S3Resource')
    def test_user_owns_bucket_handles_boto3_bucket_not_found(self, mock_s3_resource):
        s3_bucket_util = S3BucketUtil(self.endpoint, self.to_user)
        s3_bucket_util.s3.exceptions.NoSuchBucket = ValueError

        mock_s3_resource.return_value.get_bucket_owner.side_effect = ValueError

        with self.assertRaises(S3NoSuchBucket):
            s3_bucket_util.user_owns_bucket(bucket_name='test1')

    @patch('switchboard.s3_util.S3Resource')
    def test_user_owns_bucket_handles_boto3_access_denied(self, mock_s3_resource):
        s3_bucket_util = S3BucketUtil(self.endpoint, self.to_user)
        s3_bucket_util.s3.exceptions.ClientError = AccessDeniedClientError
        s3_bucket_util.s3.exceptions.NoSuchBucket = ValueError

        mock_s3_resource.return_value.get_bucket_owner.side_effect = AccessDeniedClientError

        self.assertEqual(s3_bucket_util.user_owns_bucket(bucket_name='test1'), False)

    @patch('switchboard.s3_util.S3Resource')
    def test_get_objects_manifest(self, mock_s3_resource):
        mock_last_modified = Mock()
        mock_last_modified.isoformat.return_value = '2001-01-01 12:30'
        mock_s3_resource.return_value.get_objects_for_bucket.return_value = [
            Mock(
                key='file1.txt',
                metadata={'md5':'123'},
                e_tag='sometag',
                last_modified=mock_last_modified,
                content_length=100,
                content_type='text/plain',
                version_id='1233'
            )
        ]

        s3_bucket_util = S3BucketUtil(self.endpoint, self.to_user)
        objects_manifest = s3_bucket_util.get_objects_manifest(bucket_name='test1')

        mock_s3_resource.return_value.get_objects_for_bucket.assert_called_with('test1')
        self.assertEqual(objects_manifest, [
            {
                'key': 'file1.txt',
                'content_length': 100,
                'e_tag': 'sometag',
                'version_id': '1233',
                'last_modified': '2001-01-01 12:30',
                'content_type': 'text/plain',
                'metadata': {
                    'md5': '123'
                }
            }
        ])


class AccessDeniedClientError(Exception):
    def __init__(self):
        self.response = {'Error': {'Code': 'AccessDenied'}}


class S3DeliveryTypeTestCase(TestCase):

    def setUp(self):
        self.delivery_type = S3DeliveryType()

    def test_name_and_delivery_cls(self):
        self.assertEqual(self.delivery_type.name, 's3')
        self.assertEqual(self.delivery_type.delivery_cls, S3Delivery)

    @patch('switchboard.s3_util.S3DeliveryDetails')
    def test_make_delivery_details(self, mock_delivery_details):
        mock_delivery = Mock(to_user=Mock(user='user2'))
        details = self.delivery_type.make_delivery_details(mock_delivery, 'user2')
        mock_delivery_details.assert_called_once_with(mock_delivery, 'user2')
        self.assertEqual(details, mock_delivery_details.return_value)

    @patch('switchboard.s3_util.S3DeliveryDetails')
    def test_make_delivery_details_not_recipient(self, mock_delivery_details):
        mock_delivery = Mock(to_user=Mock(user='user2'))
        with self.assertRaises(S3NotRecipientException):
            self.delivery_type.make_delivery_details(mock_delivery, 'user1')

    @patch('switchboard.s3_util.S3DeliveryUtil')
    def test_make_delivery_util(self, mock_delivery_util):
        util = self.delivery_type.make_delivery_util('s3delivery', 'user')
        mock_delivery_util.assert_called_once_with('s3delivery')
        self.assertEqual(util, mock_delivery_util.return_value)

    @patch('switchboard.s3_util.TransferBackgroundFunctions')
    def test_transfer_delivery(self, mock_background_funcs):
        mock_delivery = Mock()
        mock_delivery.id = '123'
        S3DeliveryType.transfer_delivery(mock_delivery, '')
        self.assertTrue(mock_delivery.mark_transferring.called)
        mock_background_funcs.transfer_delivery.assert_called_with(mock_delivery.id)


class S3TransferOperationTestCase(S3DeliveryTestBase):

    @patch('switchboard.s3_util.S3DeliveryUtil')
    def test_transfer_delivery_step(self, mock_s3_delivery_util):
        mock_s3_delivery_util.return_value.get_warning_message.return_value = 'warning'

        operation = S3TransferOperation(self.s3_delivery.id)
        operation.background_funcs = Mock()
        operation.transfer_delivery_step()

        self.s3_delivery.refresh_from_db()
        self.assertTrue(mock_s3_delivery_util.return_value.accept_project_transfer.called)
        self.assertTrue(mock_s3_delivery_util.return_value.share_with_additional_users.called)
        operation.background_funcs.notify_sender_delivery_accepted.assert_called_with(self.s3_delivery.id, 'warning')

    @patch('switchboard.s3_util.S3MessageFactory')
    def test_notify_sender_delivery_accepted_step(self, mock_s3_message_factory):
        mock_message = mock_s3_message_factory.return_value.make_processed_message.return_value
        mock_message.email_text = 'sender email'

        operation = S3TransferOperation(self.s3_delivery.id)
        operation.background_funcs = Mock()
        operation.notify_sender_delivery_accepted_step(warning_message='oops')

        self.s3_delivery.refresh_from_db()
        mock_s3_message_factory.return_value.make_processed_message.assert_called_with(
            'accepted', MessageDirection.ToSender, warning_message='oops')
        self.assertTrue(mock_message.send.called)
        operation.background_funcs.notify_receiver_transfer_complete.assert_called_with(
            self.s3_delivery.id, 'oops', 'sender email')

    @patch('switchboard.s3_util.S3MessageFactory')
    def test_notify_receiver_transfer_complete_step(self, mock_s3_message_factory):
        mock_message = mock_s3_message_factory.return_value.make_processed_message.return_value
        mock_message.email_text = 'receiver email'

        operation = S3TransferOperation(self.s3_delivery.id)
        operation.background_funcs = Mock()
        operation.notify_receiver_transfer_complete_step(warning_message='oops',
                                                         sender_accepted_email_text='sender email')

        self.s3_delivery.refresh_from_db()
        mock_s3_message_factory.return_value.make_processed_message.assert_called_with(
            'accepted_recipient', MessageDirection.ToRecipient, warning_message='oops')
        self.assertTrue(mock_message.send.called)
        operation.background_funcs.mark_delivery_complete.assert_called_with(
            self.s3_delivery.id, 'sender email', 'receiver email')

    def test_mark_delivery_complete_step(self):
        operation = S3TransferOperation(self.s3_delivery.id)
        operation.mark_delivery_complete_step(
            sender_accepted_email_text='sender email',
            recipient_accepted_email_text='recipient email'
        )
        self.s3_delivery.refresh_from_db()
        self.assertEqual(self.s3_delivery.state, State.ACCEPTED)

    @patch('switchboard.s3_util.S3Delivery')
    @patch('switchboard.s3_util.S3DeliveryType')
    @patch('switchboard.s3_util.S3MessageFactory')
    def test_make_processed_message(self, mock_s3_message_factory, mock_s3_delivery_type, mock_s3_delivery):
        operation = S3TransferOperation(delivery_id='delivery1')
        message = operation.make_processed_message(process_type='accepted', direction=MessageDirection.ToSender,
                                                   warning_message='warning msg')
        self.assertEqual(message, mock_s3_message_factory.return_value.make_processed_message.return_value)
        mock_s3_message_factory.return_value.make_processed_message.assert_called_with(
            'accepted', MessageDirection.ToSender, warning_message='warning msg'
        )

    @patch('switchboard.s3_util.S3Delivery')
    @patch('switchboard.s3_util.S3DeliveryType')
    def test_ensure_transferring(self, mock_s3_delivery_type, mock_s3_delivery):
        operation = S3TransferOperation(delivery_id='delivery1')
        operation.delivery.state = State.NEW
        operation.ensure_transferring()
        self.assertEqual(True, operation.delivery.mark_transferring.called)

        operation.delivery.mark_transferring.reset_mock()
        operation.delivery.state = State.TRANSFERRING
        operation.ensure_transferring()
        self.assertEqual(False, operation.delivery.mark_transferring.called)

    def test_set_failed_and_record_exception(self):
        operation = S3TransferOperation(delivery_id=self.s3_delivery.id)
        operation.set_failed_and_record_exception(ValueError("oops"))

        self.s3_delivery.refresh_from_db()
        self.assertEqual(self.s3_delivery.state, State.FAILED)
        errors = S3DeliveryError.objects.filter(delivery=self.s3_delivery)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].message, 'oops')


class SendDeliveryOperationTestCase(S3DeliveryTestBase):
    def test_run(self):
        SendDeliveryOperation.background_funcs = Mock()
        SendDeliveryOperation.run(self.s3_delivery, 'http://someurl.com')
        SendDeliveryOperation.background_funcs.record_object_manifest.assert_called_with(
            self.s3_delivery.id, 'http://someurl.com')

    @patch('switchboard.s3_util.S3BucketUtil')
    def test_record_object_manifest_step(self, mock_s3_bucket_util):
        mock_s3_bucket_util.return_value.get_objects_manifest.return_value = [{'key': '123'}]

        operation = SendDeliveryOperation(self.s3_delivery.id, 'http://someurl.com')
        operation.background_funcs = Mock()
        operation.record_object_manifest_step()

        self.s3_delivery.refresh_from_db()
        self.assertEqual(self.s3_delivery.manifest.content, [{'key': '123'}])
        operation.background_funcs.give_agent_permission.assert_called_with(self.s3_delivery.id, 'http://someurl.com')

    @patch('switchboard.s3_util.S3DeliveryUtil')
    def test_give_agent_permission_step(self, mock_s3_delivery_util):
        operation = SendDeliveryOperation(self.s3_delivery.id, 'http://someurl.com')
        operation.background_funcs = Mock()
        operation.give_agent_permission_step()

        self.assertTrue(mock_s3_delivery_util.return_value.give_agent_permissions.called)
        operation.background_funcs.send_delivery_message.assert_called_with(self.s3_delivery.id, 'http://someurl.com')

    @patch('switchboard.s3_util.S3MessageFactory')
    def test_send_delivery_message_step(self, mock_s3_message_factory):
        mock_s3_message_factory.return_value.make_delivery_message.return_value = \
            Mock(email_text='emailtxt')

        operation = SendDeliveryOperation(self.s3_delivery.id, 'http://someurl.com')
        operation.send_delivery_message_step()

        mock_s3_message_factory.return_value.make_delivery_message.assert_called_with('http://someurl.com')
        self.assertTrue(mock_s3_message_factory.return_value.make_delivery_message.return_value.send.called)

        self.s3_delivery.refresh_from_db()
        self.assertEqual(self.s3_delivery.state, State.NOTIFIED)
        self.assertEqual(self.s3_delivery.delivery_email_text, 'emailtxt')
