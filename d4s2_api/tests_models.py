from django.db import IntegrityError
from django.core import serializers
from django.test import TestCase
from d4s2_api.models import *
from django.contrib.auth.models import User
import datetime
import json


class TransferBaseTestCase(TestCase):

    def setUp(self):
        self.transfer_id = 'abcd-1234-efgh-6789'


class DeliveryTestCase(TransferBaseTestCase):
    DELIVERY_EMAIL_TEXT = 'delivery email message'
    SENDER_COMPLETE_EMAIL_TEXT = 'sender delivery accepted'
    RECIPIENT_COMPLETE_EMAIL_TEXT = 'recipient delivery accepted'
    DECLINE_EMAIL_TEXT = 'delivery declined'

    def setUp(self):
        super(DeliveryTestCase, self).setUp()
        DDSDelivery.objects.create(project_id='project1',
                                from_user_id='user1',
                                to_user_id='user2',
                                transfer_id=self.transfer_id)

    def test_initial_state(self):
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW, 'New deliveries should be in initiated state')

    def test_required_fields(self):
        with self.assertRaises(IntegrityError):
            DDSDelivery.objects.create(project_id=None, from_user_id=None, to_user_id=None, transfer_id=None)

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            DDSDelivery.objects.create(project_id='project1',
                                    from_user_id='user1',
                                    to_user_id='user2',
                                    transfer_id=self.transfer_id)

    def test_can_add_share_users(self):
        delivery = DDSDelivery.objects.create(project_id='projectA',
                                           from_user_id='user1',
                                           to_user_id='user2',
                                           transfer_id='123-123')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user4')
        share_users = delivery.share_users.all()
        self.assertEqual(set([share_user.dds_id for share_user in share_users]),
                         set(['user3', 'user4']))

    def test_user_can_be_shared_multiple_deliveries(self):
        delivery1 = DDSDelivery.objects.create(project_id='projectA',
                                            from_user_id='user1',
                                            to_user_id='user2',
                                            transfer_id='123-123')
        delivery2 = DDSDelivery.objects.create(project_id='projectB',
                                            from_user_id='user3',
                                            to_user_id='user4',
                                            transfer_id='456-789')
        DDSDeliveryShareUser.objects.create(delivery=delivery1, dds_id='user3')
        DDSDeliveryShareUser.objects.create(delivery=delivery2, dds_id='user3')
        self.assertEqual(DDSDeliveryShareUser.objects.count(), 2)
        self.assertEqual(set([share_user.dds_id for share_user in DDSDeliveryShareUser.objects.all()]),
                         set(['user3']))

    def test_user_cannot_be_shared_delivery_twice(self):
        delivery = DDSDelivery.objects.create(project_id='projectA',
                                           from_user_id='user1',
                                           to_user_id='user2',
                                           transfer_id='123-123')
        DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')
        with self.assertRaises(IntegrityError):
            DDSDeliveryShareUser.objects.create(delivery=delivery, dds_id='user3')

    def test_mark_notified(self):
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_notified(DeliveryTestCase.DELIVERY_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.NOTIFIED)

    def test_mark_accepted(self):
        performed_by = 'performer'
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_accepted(performed_by, DeliveryTestCase.SENDER_COMPLETE_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.ACCEPTED)
        self.assertEqual(delivery.performed_by, performed_by)
        self.assertEqual(delivery.sender_completion_email_text, DeliveryTestCase.SENDER_COMPLETE_EMAIL_TEXT)
        self.assertEqual(delivery.recipient_completion_email_text, '')

    def test_mark_accepted_with_recipient_email(self):
        performed_by = 'performer'
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_accepted(performed_by,
                               DeliveryTestCase.SENDER_COMPLETE_EMAIL_TEXT,
                               DeliveryTestCase.RECIPIENT_COMPLETE_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.ACCEPTED)
        self.assertEqual(delivery.performed_by, performed_by)
        self.assertEqual(delivery.sender_completion_email_text, DeliveryTestCase.SENDER_COMPLETE_EMAIL_TEXT)
        self.assertEqual(delivery.recipient_completion_email_text, DeliveryTestCase.RECIPIENT_COMPLETE_EMAIL_TEXT)

    def test_mark_declined(self):
        performed_by = 'performer'
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_declined(performed_by, 'Wrong person.',  DeliveryTestCase.DECLINE_EMAIL_TEXT)
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Wrong person.')
        self.assertEqual(delivery.performed_by, performed_by)
        self.assertEqual(delivery.sender_completion_email_text, DeliveryTestCase.DECLINE_EMAIL_TEXT)

    def test_is_complete(self):
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.is_complete(), False)
        delivery.mark_notified('')
        self.assertEqual(delivery.is_complete(), False)
        delivery.mark_accepted('', '', '')
        self.assertEqual(delivery.is_complete(), True)
        delivery.mark_declined('','','')
        self.assertEqual(delivery.is_complete(), True)
        delivery.state = State.FAILED
        delivery.save()
        self.assertEqual(delivery.is_complete(), True)

    def test_mark_transferring(self):
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_transferring()
        self.assertEqual(delivery.state, State.TRANSFERRING)
        delivery.mark_failed()
        self.assertEqual(delivery.state, State.FAILED)
        delivery.mark_transferring()
        self.assertEqual(delivery.state, State.TRANSFERRING)
        delivery.mark_accepted('', '', '')

    def test_mark_failed(self):
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.state, State.NEW)
        delivery.mark_failed()
        self.assertEqual(delivery.state, State.FAILED)

    def setup_incomplete_delivery(self):
        delivery = DDSDelivery.objects.first()
        delivery.transfer_id = self.transfer_id
        delivery.save()
        self.assertFalse(delivery.is_complete())
        return delivery

    def test_updates_local_state_accepted(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'accepted'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.ACCEPTED)
        self.assertEqual(delivery.decline_reason, '')

    def test_updates_local_state_rejected(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'rejected', 'status_comment': 'Bad Data'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Bad Data')

    def test_updates_local_state_pending(self):
        delivery = self.setup_incomplete_delivery()
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'pending'})
        self.assertFalse(delivery.is_complete())
        self.assertEqual(delivery.state, State.NEW)
        self.assertEqual(delivery.decline_reason, '')

    def test_update_without_changes(self):
        delivery = self.setup_incomplete_delivery()
        delivery.mark_declined('jsmith','Bad Data', DeliveryTestCase.DECLINE_EMAIL_TEXT)
        self.assertTrue(delivery.is_complete())
        delivery.update_state_from_project_transfer({'id': self.transfer_id, 'status': 'rejected', 'status_comment': 'Changed Comment'})
        self.assertTrue(delivery.is_complete())
        self.assertEqual(delivery.state, State.DECLINED)
        self.assertEqual(delivery.decline_reason, 'Bad Data', 'Should not change when status doesnt change')

    def test_user_message(self):
        delivery = DDSDelivery.objects.first()
        self.assertIsNone(delivery.user_message)
        user_message = 'This is the final result of analysis xyz123'
        delivery.user_message = user_message
        delivery.save()
        delivery = DDSDelivery.objects.first()
        self.assertEqual(delivery.user_message, user_message)


class ShareTestCase(TransferBaseTestCase):

    def setUp(self):
        super(ShareTestCase, self).setUp()
        Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2')

    def test_initial_state(self):
        share = Share.objects.first()
        self.assertEqual(share.state, State.NEW, 'New shares should be in initiated state')
        self.assertEqual(share.role, ShareRole.DEFAULT, 'New shares should have default role')

    def test_prohibits_duplicates(self):
        with self.assertRaises(IntegrityError):
            Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2')

    def test_allows_multiple_shares(self):
        d = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user3')
        self.assertIsNotNone(d)

    def test_allows_multiple_shares_different_roles(self):
        v = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2', role=ShareRole.VIEW)
        d = Share.objects.create(project_id='project1', from_user_id='user1', to_user_id='user2', role=ShareRole.EDIT)
        self.assertIsNotNone(v)
        self.assertIsNotNone(d)
        self.assertNotEqual(v, d)

    def test_user_message(self):
        share = Share.objects.first()
        self.assertIsNone(share.user_message)
        user_message = 'This is the preliminary result of analysis xyz123'
        share.user_message = user_message
        share.save()
        share = Share.objects.first()
        self.assertEqual(share.user_message, user_message)


class EmailTemplateTypeTestCase(TestCase):

    def requires_unique_types(self):
        EmailTemplateType.objects.create(name='type1')
        with self.assertRaises(IntegrityError):
            EmailTemplateType.objects.create(name='type1')

    def test_initial_data(self):
        """
        Data for this is loaded by a migration, make sure it's there.
        :return:
        """
        for role in ShareRole.ROLES:
            self.assertIsNotNone(EmailTemplateType.objects.get(name='share_{}'.format(role)))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='delivery'))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='accepted'))
        self.assertIsNotNone(EmailTemplateType.objects.get(name='declined'))

    def test_from_share_role(self):
        role = 'project_viewer'
        e = EmailTemplateType.from_share_role(role)
        self.assertEqual(e.name, 'share_project_viewer')


class EmailTemplateTestCase(TestCase):

    def setUp(self):
        # email templates depend on groups and users
        self.template_set = EmailTemplateSet.objects.create(name='template_set')
        self.user = User.objects.create(username='test_user')
        self.other_user = User.objects.create(username='other_user')
        UserEmailTemplateSet.objects.create(user=self.user, email_template_set=self.template_set)
        self.user_dds_id = 'user1'
        self.default_type = EmailTemplateType.from_share_role(ShareRole.DEFAULT)
        self.download_type = EmailTemplateType.from_share_role(ShareRole.DOWNLOAD)
        self.view_type = EmailTemplateType.from_share_role(ShareRole.VIEW)
        self.transfer_id = 'abc-123'

    def test_create_email_template(self):
        template = EmailTemplate.objects.create(template_set=self.template_set,
                                                owner=self.user,
                                                template_type=self.default_type,
                                                subject='Subject',
                                                body='email body')
        self.assertIsNotNone(template)

    def test_prevent_duplicate_types(self):
        template1 = EmailTemplate.objects.create(template_set=self.template_set,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        self.assertIsNotNone(template1)
        with self.assertRaises(IntegrityError):
            EmailTemplate.objects.create(template_set=self.template_set,
                                         owner=self.user,
                                         template_type=self.download_type,
                                         subject='Subject',
                                         body='email body 2')

    def test_allows_duplicate_types_outspide_group(self):
        template_set2 = EmailTemplateSet.objects.create(name='template_set2')
        template1 = EmailTemplate.objects.create(template_set=self.template_set,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        self.assertIsNotNone(template1)
        template2 = EmailTemplate.objects.create(template_set=template_set2,
                                                 owner=self.user,
                                                 template_type=self.download_type,
                                                 subject='Subject',
                                                 body='email body 1')
        # assert different items but otherwise data is the same
        self.assertIsNotNone(template2)
        self.assertNotEqual(template1, template2)
        self.assertEqual(template1.owner, template2.owner)
        self.assertEqual(template1.subject, template2.subject)
        self.assertEqual(template1.body, template2.body)
        self.assertEqual(template1.template_type, template2.template_type)
        self.assertNotEqual(template1.template_set, template2.template_set)

    def test_for_share(self):
        # Create an email template
        EmailTemplate.objects.create(template_set=self.template_set,
                                     owner=self.user,
                                     template_type=self.download_type,
                                     subject='Subject',
                                     body='email body')
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user1',
                                     to_user_id='user2',
                                     role=ShareRole.DOWNLOAD)
        t = EmailTemplate.for_share(share, self.user)
        self.assertIsNotNone(t)
        self.assertEqual(t.body, 'email body')

    def test_for_operation(self):
        # Create an email template
        delivery = DDSDelivery.objects.create(project_id='project1',
                                           from_user_id='user1',
                                           to_user_id='user2',
                                           transfer_id=self.transfer_id)
        EmailTemplate.objects.create(template_set=self.template_set,
                                     owner=self.user,
                                     template_type=EmailTemplateType.objects.get(name='accepted'),
                                     subject='Acceptance Email Subject',
                                     body='Acceptance Email Body')
        t = EmailTemplate.for_user(self.user, 'accepted')
        self.assertIsNotNone(t)
        self.assertEqual(t.subject, 'Acceptance Email Subject')

    def test_no_templates_in_template_set(self):
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user1',
                                     to_user_id='user2',
                                     role=ShareRole.DOWNLOAD)
        with self.assertRaises(EmailTemplateException) as raised_exception:
            EmailTemplate.for_share(share, self.other_user)
        self.assertEqual(str(raised_exception.exception),
                         'Setup Error: Unable to find email template for type share_file_downloader')

    def test_no_template_set_for_user(self):
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user2',
                                     to_user_id='user1',
                                     role=ShareRole.DOWNLOAD)
        with self.assertRaises(EmailTemplateException) as raised_exception:
            EmailTemplate.for_share(share, self.other_user)
        self.assertEqual(str(raised_exception.exception),
                         'Setup Error: Unable to find email template for type share_file_downloader')
        """        share = Share.objects.create(project_id='project1',
                                     from_user_id='user2',
                                     to_user_id='user1',
                                     role=ShareRole.DOWNLOAD)
        default_email_template_set = EmailTemplateSet.objects.create(name=DEFAULT_EMAIL_TEMPLATE_SET_NAME)
        some_email_template = EmailTemplate.objects.create(template_set=default_email_template_set,
                                                           owner=self.user,
                                                           template_type=self.download_type,
                                                           subject='Subject',
                                                           body='email body')
        email_template = EmailTemplate.for_share(share)
        self.assertEqual(email_template.id, some_email_template.id)"""

    def test_no_template_set_for_user_if_default_setup(self):
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user2',
                                     to_user_id='user1',
                                     role=ShareRole.DOWNLOAD)
        default_email_template_set = EmailTemplateSet.objects.create(name=DEFAULT_EMAIL_TEMPLATE_SET_NAME)
        some_email_template = EmailTemplate.objects.create(template_set=default_email_template_set,
                                                           owner=self.user,
                                                           template_type=self.download_type,
                                                           subject='Subject',
                                                           body='email body')
        email_template = EmailTemplate.for_share(share, self.other_user)
        self.assertEqual(email_template.id, some_email_template.id)

    def test_user_not_found(self):
        # dds_user2 is not bound to a django user, so we can't find templates
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user2',
                                     to_user_id='user1',
                                     role=ShareRole.DOWNLOAD)
        with self.assertRaises(EmailTemplateException) as raised_exception:
            EmailTemplate.for_share(share, self.other_user)
        self.assertEqual(str(raised_exception.exception),
                         'Setup Error: Unable to find email template for type share_file_downloader')

    def test_user_not_found_if_we_create_default(self):
        share = Share.objects.create(project_id='project1',
                                     from_user_id='user2',
                                     to_user_id='user1',
                                     role=ShareRole.DOWNLOAD)
        default_email_template_set = EmailTemplateSet.objects.create(name=DEFAULT_EMAIL_TEMPLATE_SET_NAME)
        some_email_template = EmailTemplate.objects.create(template_set=default_email_template_set,
                                                           owner=self.user,
                                                           template_type=self.download_type,
                                                           subject='Subject',
                                                           body='email body')
        email_template = EmailTemplate.for_share(share, self.other_user)
        self.assertEqual(email_template.id, some_email_template.id)


class S3EndpointTestCase(TestCase):
    def test_create_and_read(self):
        s3_url = 'https://s3service.com/'
        S3Endpoint.objects.create(url=s3_url)
        s3_endpoints = S3Endpoint.objects.all()
        self.assertEqual(len(s3_endpoints), 1)
        self.assertEqual(s3_endpoints[0].url, s3_url)

    def test_deserialization_with_get_by_natural_key(self):
        s3_endpoint_json_ary = '[{"model": "d4s2_api.s3endpoint", "fields": {"url": "https://s3.com/"}}]'
        s3_endpoint_list = list(serializers.deserialize("json", s3_endpoint_json_ary))
        self.assertEqual(len(s3_endpoint_list), 1)
        s3_endpoint_list[0].save()
        s3_endpoints = S3Endpoint.objects.all()
        self.assertEqual(len(s3_endpoints), 1)
        self.assertEqual(s3_endpoints[0].url, "https://s3.com/")


class S3UserTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='user1')
        self.user2 = User.objects.create(username='user2')

    def test_create_and_read(self):
        endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        s3_user1 = S3User.objects.create(endpoint=endpoint,
                                         s3_id='user1_s3_id',
                                         user=self.user1)
        self.assertEqual(s3_user1.type, S3UserTypes.NORMAL)
        self.assertEqual(s3_user1.get_type_label(), 'Normal')

        s3_user2 = S3User.objects.create(endpoint=endpoint,
                                         s3_id='user1_s3_id',
                                         user=self.user2,
                                         type=S3UserTypes.AGENT)
        self.assertEqual(s3_user2.type, S3UserTypes.AGENT)
        self.assertEqual(s3_user2.get_type_label(), 'Agent')

        s3_users = S3User.objects.order_by('s3_id')
        self.assertEqual(len(s3_users), 2)
        self.assertEqual([s3_user.s3_id for s3_user in s3_users],
                         ['user1_s3_id','user1_s3_id'])

    def test_duplicating_endoint_and_user(self):
        # One django user can have multiple S3Users as long as the endpoints are different
        endpoint1 = S3Endpoint.objects.create(url='https://s3service1.com/', name='primary')
        endpoint2 = S3Endpoint.objects.create(url='https://s3service2.com/', name='secondary')

        S3User.objects.create(endpoint=endpoint1, s3_id='user1_s3_id', user=self.user1)
        S3User.objects.create(endpoint=endpoint2, s3_id='user1_s3_2id', user=self.user1)

        with self.assertRaises(IntegrityError):
            S3User.objects.create(endpoint=endpoint1, s3_id='user1_s3_3id', user=self.user1)

    def test_endpoint_name_must_be_unique(self):
        # One django user can have multiple S3Users as long as the endpoints are different
        endpoint1 = S3Endpoint.objects.create(url='https://s3service1.com/', name='primary')
        with self.assertRaises(IntegrityError):
            S3Endpoint.objects.create(url='https://s3service2.com/', name='primary')


class S3UserCredentialTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='user1')
        self.endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user1_s3_id',
                                              user=self.user1)

    def test_create_and_read(self):
        S3UserCredential.objects.create(s3_user=self.s3_user1, aws_secret_access_key='secret123')
        s3_user_credentials = S3UserCredential.objects.all()
        self.assertEqual(len(s3_user_credentials), 1)
        self.assertEqual(s3_user_credentials[0].aws_secret_access_key, 'secret123')
        self.assertEqual(s3_user_credentials[0].s3_user, self.s3_user1)

    def test_creating_multiple_credentials_for_one_user(self):
        S3UserCredential.objects.create(s3_user=self.s3_user1, aws_secret_access_key='secret123')
        with self.assertRaises(IntegrityError):
            S3UserCredential.objects.create(s3_user=self.s3_user1, aws_secret_access_key='secret124')


class S3BucketTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='user1')
        self.endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user1_s3_id',
                                              user=self.user1)

    def test_create_and_read(self):
        S3Bucket.objects.create(name='mouse', owner=self.s3_user1, endpoint=self.endpoint)
        S3Bucket.objects.create(name='mouse2', owner=self.s3_user1, endpoint=self.endpoint)
        S3Bucket.objects.create(name='mouse3', owner=self.s3_user1, endpoint=self.endpoint)
        s3_buckets = S3Bucket.objects.order_by('name')
        self.assertEqual(len(s3_buckets), 3)
        self.assertEqual([s3_bucket.name for s3_bucket in s3_buckets],
                         ['mouse', 'mouse2', 'mouse3'])

    def test_prevents_duplicate_name_endpoint(self):
        S3Bucket.objects.create(name='mouse', owner=self.s3_user1, endpoint=self.endpoint)
        with self.assertRaises(IntegrityError):
            S3Bucket.objects.create(name='mouse', owner=self.s3_user1, endpoint=self.endpoint)


class S3DeliveryCredentialTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='user1')
        self.user2 = User.objects.create(username='user2')
        self.endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user1_s3_id',
                                              user=self.user1)
        self.s3_user2 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user2_s3_id',
                                              user=self.user2)
        self.s3_bucket = S3Bucket.objects.create(name='mouse', owner=self.s3_user1, endpoint=self.endpoint)
        self.s3_bucket2 = S3Bucket.objects.create(name='mouse2', owner=self.s3_user1, endpoint=self.endpoint)

    def test_create_and_read(self):
        S3Delivery.objects.create(bucket=self.s3_bucket, from_user=self.s3_user1, to_user=self.s3_user2)
        S3Delivery.objects.create(bucket=self.s3_bucket2, from_user=self.s3_user1, to_user=self.s3_user2)
        s3_deliveries = S3Delivery.objects.order_by('bucket__name')
        self.assertEqual([s3_delivery.bucket.name for s3_delivery in s3_deliveries],
                         ['mouse', 'mouse2'])

    def test_prevents_creating_same_delivery_twice(self):
        S3Delivery.objects.create(bucket=self.s3_bucket, from_user=self.s3_user1, to_user=self.s3_user2)
        with self.assertRaises(IntegrityError):
            S3Delivery.objects.create(bucket=self.s3_bucket, from_user=self.s3_user1, to_user=self.s3_user2)


class DDSDeliveryErrorTestCase(TestCase):
    def setUp(self):
        self.delivery1 = DDSDelivery.objects.create(
            project_id='project1',
            from_user_id='user1',
            to_user_id='user2',
            transfer_id='transfer1')
        self.delivery2 = DDSDelivery.objects.create(
            project_id='project2',
            from_user_id='user2',
            to_user_id='user3',
            transfer_id='transfer2')

    def test_create_errors(self):
        DDSDeliveryError.objects.create(message='Something failed', delivery=self.delivery1)
        DDSDeliveryError.objects.create(message='Other failed', delivery=self.delivery1)
        deliveries = DDSDeliveryError.objects.order_by('message')
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0].message, 'Other failed')
        self.assertIsNotNone(deliveries[0].created)
        self.assertEqual(type(deliveries[0].created), datetime.datetime)
        self.assertEqual(deliveries[1].message, 'Something failed')
        self.assertIsNotNone(deliveries[1].created)
        self.assertEqual(type(deliveries[1].created), datetime.datetime)

    def test_read_via_delivery_errors(self):
        DDSDeliveryError.objects.create(message='Error1', delivery=self.delivery1)
        DDSDeliveryError.objects.create(message='Error2', delivery=self.delivery1)
        DDSDeliveryError.objects.create(message='Error3OtherDelivery', delivery=self.delivery2)

        deliveries = self.delivery1.errors.order_by('message')
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0].message, 'Error1')
        self.assertEqual(deliveries[1].message, 'Error2')


class S3DeliveryErrorTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='user1')
        self.user2 = User.objects.create(username='user2')
        self.endpoint = S3Endpoint.objects.create(url='https://s3service.com/')
        self.s3_user1 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user1_s3_id',
                                              user=self.user1)
        self.s3_user2 = S3User.objects.create(endpoint=self.endpoint,
                                              s3_id='user2_s3_id',
                                              user=self.user2)
        self.s3_bucket = S3Bucket.objects.create(name='mouse', owner=self.s3_user1, endpoint=self.endpoint)
        self.s3_bucket2 = S3Bucket.objects.create(name='mouse2', owner=self.s3_user1, endpoint=self.endpoint)
        self.delivery1 = S3Delivery.objects.create(bucket=self.s3_bucket,
                                                   from_user=self.s3_user1, to_user=self.s3_user2)
        self.delivery2 = S3Delivery.objects.create(bucket=self.s3_bucket2,
                                                   from_user=self.s3_user1, to_user=self.s3_user2)

    def test_create_errors(self):
        S3DeliveryError.objects.create(message='Something failed', delivery=self.delivery1)
        S3DeliveryError.objects.create(message='Other failed', delivery=self.delivery1)
        deliveries = S3DeliveryError.objects.order_by('message')
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0].message, 'Other failed')
        self.assertIsNotNone(deliveries[0].created)
        self.assertEqual(type(deliveries[0].created), datetime.datetime)
        self.assertEqual(deliveries[1].message, 'Something failed')
        self.assertIsNotNone(deliveries[1].created)
        self.assertEqual(type(deliveries[1].created), datetime.datetime)

    def test_ead_via_delivery_errors(self):
        S3DeliveryError.objects.create(message='Error1', delivery=self.delivery1)
        S3DeliveryError.objects.create(message='Error2', delivery=self.delivery1)
        S3DeliveryError.objects.create(message='Error3OtherDelivery', delivery=self.delivery2)

        deliveries = self.delivery1.errors.order_by('message')
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0].message, 'Error1')
        self.assertEqual(deliveries[1].message, 'Error2')
