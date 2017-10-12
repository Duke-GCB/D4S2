from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from rest_framework import serializers

from d4s2_api.models import Delivery, Share, DukeDSUser, DukeDSProject


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


class DeliverySerializer(serializers.HyperlinkedModelSerializer):
    project_id = CreatableSlugRelatedField(source='project', slug_field='project_id',
                                           queryset=DukeDSProject.objects.all())
    from_user_id = CreatableSlugRelatedField(source='from_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())
    to_user_id = CreatableSlugRelatedField(source='to_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())

    class Meta:
        model = Delivery
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'state', 'transfer_id', 'user_message',)


class ShareSerializer(serializers.HyperlinkedModelSerializer):
    project_id = CreatableSlugRelatedField(source='project', slug_field='project_id',
                                           queryset=DukeDSProject.objects.all())
    from_user_id = CreatableSlugRelatedField(source='from_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())
    to_user_id = CreatableSlugRelatedField(source='to_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())

    class Meta:
        model = Share
        fields = ('id', 'url', 'project_id', 'from_user_id', 'to_user_id', 'role', 'state', 'user_message',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all())

    class Meta:
        model = DukeDSUser
        fields = ('id', 'user_id', 'url', 'dds_id', 'full_name', 'email')
