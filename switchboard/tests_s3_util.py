from django.test import TestCase
from mock import patch, Mock, call
from d4s2_api.models import S3UserTypes, S3User, S3Delivery, User
from switchboard.s3_util import S3Resource


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



