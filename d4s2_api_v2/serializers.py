from rest_framework import serializers
from django.contrib.auth.models import User
from switchboard.dds_util import DDSUtil
from d4s2_api.models import S3Endpoint, S3User, S3Bucket, S3Delivery, EmailTemplateSet, UserEmailTemplateSet, EmailTemplate
from d4s2_api_v2.models import DDSDeliveryPreview


class DDSUserSerializer(serializers.Serializer):
    """
    Serializer for DukeDS users API
    """
    id = serializers.UUIDField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()

    class Meta:
        resource_name = 'duke-ds-users'


class DDSProjectSerializer(serializers.Serializer):
    """
    Serializer for DukeDS projects API
    """
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    is_deleted = serializers.BooleanField()
    url = serializers.URLField()
    created_on = serializers.DateField()
    last_updated_on = serializers.DateField()

    class Meta:
        resource_name = 'duke-ds-projects'


class DDSProjectSummarySerializer(DDSProjectSerializer):
    total_size = serializers.IntegerField()
    file_count = serializers.IntegerField()
    folder_count = serializers.IntegerField()
    root_folder_count = serializers.IntegerField()

    class Meta:
        resource_name = 'duke-ds-project-summaries'


class DDSProjectTransferSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    status_comment = serializers.CharField(allow_null=True)
    to_users = DDSUserSerializer(many=True)
    from_user = DDSUserSerializer()
    project = DDSProjectSerializer()
    delivery = serializers.UUIDField()
    created_on = serializers.DateTimeField()
    last_updated_on = serializers.DateTimeField()

    class Meta:
        resource_name = 'duke-ds-project-transfers'


class DDSProjectPermissionSerializer(serializers.Serializer):
    id = serializers.CharField()
    project = serializers.UUIDField()
    user = serializers.UUIDField()
    auth_role = serializers.UUIDField()

    class Meta:
        resource_name = 'duke-ds-project-permissions'


class UserSerializer(serializers.ModelSerializer):
    setup_for_delivery = serializers.SerializerMethodField()

    def get_setup_for_delivery(self, user):
        return UserEmailTemplateSet.user_is_setup(user)

    class Meta:
        model = User
        resource_name = 'users'
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'setup_for_delivery')


class S3EndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = S3Endpoint
        resource_name = 's3endpoints'
        fields = ('id', 'url', 'name',)


class S3UserSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email')
    type = serializers.CharField(source='get_type_label')

    class Meta:
        model = S3User
        resource_name = 's3users'
        fields = ('id', 'user', 'endpoint', 'email', 'type')


class S3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = S3Bucket
        resource_name = 's3bucket'
        fields = ('id', 'name', 'owner', 'endpoint')

    def validate_owner(self, owner):
        # this method is automatically picked up and run by the serializer for validating the owner field
        if owner.user != self.context['request'].user:
            raise serializers.ValidationError(str("You must be the owner of buckets you create."))
        return owner

    def validate(self, data):
        owner = data['owner']
        endpoint = data['endpoint']
        if owner.endpoint != endpoint:
            raise serializers.ValidationError(str("The owner belongs to a different endpoint, they should match."))
        return data


class S3DeliverySerializer(serializers.ModelSerializer):
    email_template_set = serializers.PrimaryKeyRelatedField(queryset=EmailTemplateSet.objects.all(), required=False)

    class Meta:
        model = S3Delivery
        resource_name = 's3delivery'
        fields = ('id', 'bucket', 'from_user', 'to_user', 'state', 'user_message',
                  'decline_reason', 'performed_by', 'delivery_email_text', 'transfer_id', 'email_template_set')
        read_only_fields = ('state', 'decline_reason', 'performed_by', 'delivery_email_text', 'transfer_id',
                            'email_template_set')

    def validate_from_user(self, from_user):
        if from_user.user != self.context['request'].user:
            raise serializers.ValidationError(str("You must be the from user of s3 deliveries you create."))
        return from_user

    def validate(self, data):
        bucket = data['bucket']
        from_user = data['from_user']
        to_user = data['to_user']
        if bucket.endpoint != from_user.endpoint or bucket.endpoint != to_user.endpoint:
            raise serializers.ValidationError(str("Users and bucket should all have the same endpoint."))
        if from_user == to_user:
            raise serializers.ValidationError(str("You cannot send s3 delivery to yourself."))
        return data


class DDSDeliveryPreviewSerializer(serializers.Serializer):
    """
    A serializer to represent a delivery preview, allowing for
    email generation before saving to database or creating a transfer in DukeDS
    transfer_id must be provided but may be blank.
    For new deliveries it won't be known before creating the transfer in DukeDS, but for
    resending existing deliveries, it can be provided and will be used in the accept url
    """
    from_user_id = serializers.CharField(required=True)
    to_user_id = serializers.CharField(required=True)
    project_id = serializers.CharField(required=True)
    transfer_id = serializers.CharField(allow_blank=True)
    user_message = serializers.CharField(allow_blank=True)
    delivery_email_text = serializers.CharField(read_only=True)

    class Meta:
        resource_name = 'delivery-preview'


class DDSAuthProviderSerializer(serializers.Serializer):
    """
    Serializer for DukeDS auth provider affiliates API
    """
    id = serializers.UUIDField()
    service_id = serializers.UUIDField()
    name = serializers.CharField()
    is_deprecated = serializers.BooleanField()
    is_default = serializers.BooleanField()
    login_initiation_url = serializers.CharField()

    class Meta:
        resource_name = 'duke-ds-auth-provider'


class DDSAffiliateSerializer(serializers.Serializer):
    """
    Serializer for DukeDS auth provider affiliates API
    """
    uid = serializers.CharField()
    full_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()

    class Meta:
        resource_name = 'duke-ds-auth-provider-affiliates'


class AddUserSerializer(serializers.Serializer):
    username = serializers.CharField()


class EmailTemplateSetSerializer(serializers.ModelSerializer):
    email_templates = serializers.SerializerMethodField()
    default = serializers.SerializerMethodField()

    def get_email_templates(self, obj):
        return [x.id for x in obj.email_templates.order_by('template_type__sequence')]

    def get_default(self, obj):
        return UserEmailTemplateSet.objects.filter(
            email_template_set=obj,
            user=self.context['request'].user
        ).exists()

    class Meta:
        model = EmailTemplateSet
        resource_name = 'email-template-set'
        fields = ('id', 'name', 'cc_address', 'reply_address', 'email_templates', 'default')


class EmailTemplateSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    help_text = serializers.SerializerMethodField()

    def get_type(self, obj):
        return obj.template_type.name

    def get_help_text(self, obj):
        return obj.template_type.help_text

    class Meta:
        model = EmailTemplate
        resource_name = 'email-template'
        fields = ('id', 'template_set', 'owner', 'type', 'help_text', 'body', 'subject')
