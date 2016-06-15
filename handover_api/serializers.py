from handover_api.models import Handover, Draft, DukeDSUser, DukeDSProject
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from rest_framework import serializers


class CreatableSlugField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        try:
            return self.get_queryset().get_or_create(**{self.slug_field: data})[0]
        except ObjectDoesNotExist:
            self.fail('does_not_exist', slug_name=self.slug_field, value=smart_text(data))
        except (TypeError, ValueError):
            self.fail('invalid')

class HandoverSerializer(serializers.HyperlinkedModelSerializer):
    project_id = CreatableSlugField(source='project', slug_field='project_id', queryset=DukeDSProject.objects.all())
    from_user_id = CreatableSlugField(source='from_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())
    to_user_id = CreatableSlugField(source='to_user', slug_field='dds_id', queryset=DukeDSUser.objects.all())

    class Meta:
        model = Handover
        fields = ('id','url','project_id','from_user_id','to_user_id','state')


class DraftSerializer(serializers.HyperlinkedModelSerializer):
    project_id = serializers.StringRelatedField(source='project.project_id', read_only=True)
    from_user_id = serializers.StringRelatedField(source='from_user.dds_id', read_only=True)
    to_user_id = serializers.StringRelatedField(source='to_user.dds_id', read_only=True)

    class Meta:
        model = Draft
        fields = ('id','url','project_id','from_user_id','to_user_id','state')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all())
    class Meta:
        model = DukeDSUser
        fields = ('id', 'user_id','url','dds_id', 'api_key', 'full_name', 'email')