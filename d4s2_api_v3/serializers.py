from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()

    class Meta:
        resource_name = 'users'


class ProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    url = serializers.URLField()
    created_on = serializers.DateField()
    last_updated_on = serializers.DateField()
    backend = serializers.CharField()

    class Meta:
        resource_name = 'projects'
