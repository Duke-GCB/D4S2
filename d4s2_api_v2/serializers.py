from rest_framework import serializers
from django.contrib.auth.models import User
from switchboard.dds_util import DDSUtil
from d4s2_api.models import S3Endpoint, S3User, S3Bucket, S3Delivery
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

    class Meta:
        resource_name = 'duke-ds-projects'


class DDSProjectTransferSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    status_comment = serializers.CharField(allow_null=True)
    to_users = DDSUserSerializer(many=True)
    from_user = DDSUserSerializer()
    project = DDSProjectSerializer()
    delivery = serializers.UUIDField()

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
    class Meta:
        model = User
        resource_name = 'users'
        fields = ('id', 'username', 'first_name', 'last_name', 'email')


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
    class Meta:
        model = S3Delivery
        resource_name = 's3delivery'
        fields = ('id', 'bucket', 'from_user', 'to_user', 'state', 'user_message',
                  'decline_reason', 'performed_by', 'delivery_email_text', 'transfer_id',)
        read_only_fields = ('state', 'decline_reason', 'performed_by', 'delivery_email_text', 'transfer_id',)

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
