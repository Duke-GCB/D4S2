from handover_api.models import Handover, Draft, DukeDSUser
from django.contrib.auth.models import User
from rest_framework import serializers


class HandoverSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Handover
        fields = ('id','url','project_id','from_user_id','to_user_id','state')


class DraftSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Draft
        fields = ('id','url','project_id','from_user_id','to_user_id','state')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all())
    class Meta:
        model = DukeDSUser
        fields = ('id', 'user_id','url','dds_id', 'api_key', 'full_name', 'email')