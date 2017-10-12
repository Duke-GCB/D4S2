from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_text
from models import Delivery, DukeDSUser, DukeDSProject

from rest_framework import serializers


class DeliverySerializer(serializers.ModelSerializer):

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
