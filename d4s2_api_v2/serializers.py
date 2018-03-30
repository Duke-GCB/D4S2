from rest_framework import serializers
from django.contrib.auth.models import User
from switchboard.dds_util import DDSUtil


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
