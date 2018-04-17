from django.test import TestCase
from mock import patch, Mock, call
from d4s2_api.models import S3Bucket, S3User, S3UserTypes, S3Delivery, User, S3Endpoint
from switchboard.s3_util import S3Resource, S3DeliveryUtil


class S3DeliveryUtilTestCase(TestCase):
    def setUp(self):
        self.user_agent = User.objects.create(username='agent')
        self.from_user = User.objects.create(username='from_user')
        self.to_user = User.objects.create(username='to_user')
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
        self.s3_bucket = S3Bucket.objects.create(name='mouse', owner=self.s3_from_user, endpoint=self.endpoint)
        self.s3_delivery = S3Delivery.objects.create(bucket=self.s3_bucket,
                                                     from_user=self.s3_from_user,
                                                     to_user=self.s3_to_user)

    def test_s3_agent_property(self):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.from_user)
        s3_agent = s3_delivery_util.s3_agent
        self.assertEqual(s3_agent.type, S3UserTypes.AGENT)
        self.assertEqual(s3_agent.id, self.s3_agent_user.id)

    def test_s3_current_user_property(self):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.from_user)
        current_s3_user = s3_delivery_util.current_s3_user
        self.assertEqual(current_s3_user.type, S3UserTypes.NORMAL)
        self.assertEqual(current_s3_user.id, self.s3_from_user.id)

    def test_destination_bucket_name_property(self):
        self.s3_bucket.name = 'mouse'
        self.s3_bucket.save()
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.from_user)
        destination_bucket_name = s3_delivery_util.destination_bucket_name
        self.assertEqual(destination_bucket_name, 'delivery_mouse')

        self.s3_bucket.name = 'ThisBucket'
        self.s3_bucket.save()
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.from_user)
        destination_bucket_name = s3_delivery_util.destination_bucket_name
        self.assertEqual(destination_bucket_name, 'delivery_ThisBucket')

    @patch('switchboard.s3_util.S3Resource')
    def test_give_agent_permissions(self, mock_s3_resource):
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.from_user)
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

        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.to_user)
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
        s3_delivery_util = S3DeliveryUtil(self.s3_delivery, self.to_user)
        s3_delivery_util.decline_delivery()
        mock_s3_resource.return_value.grant_bucket_acl.assert_called_with(
            'mouse', grant_full_control_user=self.s3_from_user
        )


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
        mock_destination_bucket = Mock()
        mock_bucket_constructor = mock_boto3.session.Session.return_value.resource.return_value.Bucket
        mock_bucket_constructor.side_effect = [
            mock_source_bucket,
            mock_destination_bucket,
        ]

        s3_resource = S3Resource(self.s3_user)
        s3_resource.copy_bucket(source_bucket_name='from_bucket', destination_bucket_name='to_bucket')

        mock_bucket_constructor.assert_has_calls([
            call('from_bucket'), call('to_bucket')
        ])
        mock_destination_bucket.copy.assert_has_calls([
            call(CopySource={'Bucket': 'from_bucket', 'Key': 'key1'}, Key='key1'),
            call(CopySource={'Bucket': 'from_bucket', 'Key': 'key2'}, Key='key2')
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
