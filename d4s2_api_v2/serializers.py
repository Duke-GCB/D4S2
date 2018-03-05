from rest_framework import serializers


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

    class Meta:
        resource_name = 'duke-ds-project-transfers'
