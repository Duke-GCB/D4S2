from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from rest_framework import serializers

from d4s2_api.models import Delivery, Share, DukeDSUser, DeliveryShareUser
SHARE_USERS_INVALID_MSG = "to_user cannot be part of share_to_users."


def validate_delivery_data(data):
    """
    Check that to_user_id is not accidentally included in share_user_ids
    """
    to_user_id = data['to_user_id']
    share_user_ids = data.get('share_user_ids', [])
    if share_user_ids:
        if to_user_id in share_user_ids:
            raise serializers.ValidationError(SHARE_USERS_INVALID_MSG)
    return data


class DeliverySerializer(serializers.HyperlinkedModelSerializer):
    share_user_ids = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, data):
        return validate_delivery_data(data)

    def to_representation(self, instance):
        ret = super(DeliverySerializer, self).to_representation(instance)
        ret['share_user_ids'] = [share_user.dds_id for share_user in instance.share_users.all()]
        return ret

    def create(self, validated_data):
        delivery_data = self._remove_share_user_ids_from_dict(validated_data)
        instance = super(DeliverySerializer, self).create(delivery_data)
        if 'share_user_ids' in validated_data:
            self._update_share_users(validated_data['share_user_ids'], instance)
        return instance

    def update(self, instance, validated_data):
        delivery_data = self._remove_share_user_ids_from_dict(validated_data)
        instance = super(DeliverySerializer, self).update(instance, delivery_data)
        if 'share_user_ids' in validated_data:
            self._update_share_users(validated_data['share_user_ids'], instance)
        return instance

    @staticmethod
    def _remove_share_user_ids_from_dict(validated_data):
        delivery_data = dict(validated_data)
        if 'share_user_ids' in delivery_data:
            delivery_data.pop('share_user_ids')
        return delivery_data

    @staticmethod
    def _update_share_users(share_user_ids, delivery):
        DeliveryShareUser.objects.filter(delivery=delivery).delete()
        for share_user_id in share_user_ids:
            DeliveryShareUser.objects.create(delivery=delivery, dds_id=share_user_id)

    class Meta:
        model = Delivery
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'state', 'transfer_id', 'user_message',
                  'share_user_ids')


class ShareSerializer(serializers.HyperlinkedModelSerializer):
    def validate(self, data):
        return validate_delivery_data(data)

    class Meta:
        model = Share
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'role', 'state', 'user_message',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all())

    class Meta:
        model = DukeDSUser
        fields = ('id', 'user_id', 'url', 'dds_id', 'full_name', 'email')


class DDSUserSerializer(serializers.Serializer):
    """
    Serializer for dds_resources.DDSProject
    """
    id = serializers.UUIDField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()

    class Meta:
        resource_name = 'dds-users'


class DDSProjectSerializer(serializers.Serializer):
    """
    Serializer for dds_resources.DDSProject
    """
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()

    class Meta:
        resource_name = 'dds-projects'



