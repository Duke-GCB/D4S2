from models import Handover, Draft, User
from rest_framework import serializers


class HandoverSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Handover
        fields = ('project_id','from_user_id','to_user_id','state')


class DraftSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Draft
        fields = ('project_id','from_user_id','to_user_id','state')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('dds_id', 'api_key')