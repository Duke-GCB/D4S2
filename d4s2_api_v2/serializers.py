from rest_framework import serializers
from django.contrib.auth.models import User
from switchboard.dds_util import DDSUtil
from d4s2_api.models import S3Endpoint, S3User, S3Bucket, S3Delivery


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


class UserSerializer(serializers.ModelSerializer):
    duke_ds_user = serializers.SerializerMethodField()

    class Meta:
        model = User
        resource_name = 'users'
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'duke_ds_user',)

    @staticmethod
    def get_duke_ds_user(user):
        return DDSUtil(user).get_current_user().id


class S3EndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = S3Endpoint
        resource_name = 's3endpoints'
        fields = ('id', 'url',)


class S3UserSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = S3User
        resource_name = 's3users'
        fields = ('id', 'user', 'endpoint', 'email', 'type')

    @staticmethod
    def get_email(s3_user):
        return s3_user.user.email

    @staticmethod
    def get_type(s3_user):
        return s3_user.get_type_label()


class S3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = S3Bucket
        resource_name = 's3bucket'
        fields = ('id', 'name', 'owner', 'endpoint')

    def validate_owner(self, owner):
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
                  'decline_reason', 'performed_by', 'delivery_email_text')
        read_only_fields = ('state', 'decline_reason', 'performed_by', 'delivery_email_text',)

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
