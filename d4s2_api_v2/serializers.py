from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from d4s2_api_v2.models import Delivery, DukeDSUser, DukeDSProject
from d4s2_api.serializers import validate_delivery_data

from rest_framework import serializers


class DeliverySerializer(serializers.ModelSerializer):
    def validate(self, data):
        return validate_delivery_data(data)

    class Meta:
        model = Delivery
        resource_name = 'deliveries'
        fields = '__all__'


class DukeDSUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = DukeDSUser
        resource_name = 'duke-ds-users'
        fields = '__all__'


class DukeDSProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = DukeDSProject
        resource_name = 'duke-ds-projects'
        fields = '__all__'
