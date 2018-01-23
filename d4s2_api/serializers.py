from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from rest_framework import serializers

from d4s2_api.models import Delivery, Share, DukeDSUser, DeliveryShareUser
SHARE_USERS_INVALID_MSG = "to_user cannot be part of share_to_users."


class CreatableSlugRelatedField(serializers.SlugRelatedField):
    """
    SlugRelatedField (parent) is a read-write field that represents the target of a
    relationship by a unique 'slug' attribute.

    For example, serialized Delivery objects include the project's DukeDS UUID. This UUID is not stored
    in the Delivery model, it is stored in the DukeDSProject model. SlugRelatedField makes this UUID part
    of the serialized Delivery.

    SlugRelatedField supports reading and writing. Changing a Delivery's project_id through the REST API
    will associate the delivery with a different DukeDSProject object.

    CreatableSlugRelatedField extends SlugRelatedField with the ability to create new model objects
    with the slug data when they don't already exist.

    From http://stackoverflow.com/a/28011896
    """

    def to_internal_value(self, data):
        try:
            return self.get_queryset().get_or_create(**{self.slug_field: data})[0]
        except ObjectDoesNotExist:
            self.fail('does_not_exist', slug_name=self.slug_field, value=smart_text(data))
        except (TypeError, ValueError):
            self.fail('invalid')


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

    def create(self, validated_data):
        delivery_data = self._remove_share_user_ids(validated_data)
        instance = super(DeliverySerializer, self).create(delivery_data)
        if 'share_user_ids' in validated_data:
            self._update_share_users(validated_data['share_user_ids'], instance)
        return instance

    def update(self, instance, validated_data):
        delivery_data = self._remove_share_user_ids(validated_data)
        instance = super(DeliverySerializer, self).update(instance, delivery_data)
        if 'share_user_ids' in validated_data:
            self._update_share_users(validated_data['share_user_ids'], instance)
        return instance

    @staticmethod
    def _remove_share_user_ids(validated_data):
        delivery_data = dict(validated_data)
        if 'share_user_ids' in delivery_data:
            delivery_data.pop('share_user_ids')
        return delivery_data

    @staticmethod
    def _update_share_users(share_user_ids, delivery):
        DeliveryShareUser.objects.filter(delivery=delivery).delete()
        for share_user_id in share_user_ids:
            DeliveryShareUser.objects.create(delivery=delivery, dds_id=share_user_id)

    @staticmethod
    def _split_validated_data(validated_data):
        """
        Split validated data into a dictionary of validated data and the share_user_ids
        :param validated_data: dict that may contain 'share_user_ids'
        :return: (dict, [str]): tuple where first element is updated validated_data, second is share_user_ids
        """
        delivery_data = dict(validated_data)
        share_user_ids = []
        if 'share_user_ids' in delivery_data:
            share_user_ids = delivery_data.pop('share_user_ids')
        return delivery_data, validated_data

    class Meta:
        model = Delivery
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'state', 'transfer_id', 'user_message',
                  'share_user_ids')


class ShareSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Share
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'role', 'state', 'user_message',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all())

    class Meta:
        model = DukeDSUser
        fields = ('id', 'user_id', 'url', 'dds_id', 'full_name', 'email')
