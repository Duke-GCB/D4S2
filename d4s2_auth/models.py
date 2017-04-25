from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User
import json


class OAuthService(models.Model):
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    client_id = models.CharField(max_length=64, null=False, blank=False)
    client_secret = models.CharField(max_length=64, null=False, blank=False)
    authorization_uri = models.URLField(null=False, blank=False)
    token_uri = models.URLField(null=False, blank=False)
    resource_uri = models.URLField(null=False, blank=False)
    redirect_uri = models.URLField(null=False, blank=False)
    revoke_uri = models.URLField(null=False, blank=False)
    scope = models.CharField(max_length=64, null=False, blank=False)

    def __unicode__(self):
        return 'OAuth Service {}, Auth URL: {}'.format(self.name, self.authorization_uri)


class OAuthToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(OAuthService, on_delete=models.CASCADE)
    token_json = models.TextField()

    @property
    def token_dict(self):
        return json.loads(self.token_json)

    @token_dict.setter
    def token_dict(self, value):
        self.token_json = json.dumps(value)

    class Meta:
        unique_together = [
            ('user', 'service'),     # User may only have one token here per service
            ('service', 'token_json'),   # Token+service unique ensures only one user per token/service pair
        ]
        # But we must allow user+token to be the same when the service is different


class OAuthState(models.Model):
    state = models.CharField(max_length=64, null=False, blank=False, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    destination = models.CharField(max_length=200, blank=True)


class DukeDSAPIToken(models.Model):
    """
    A token for a user that can be used for authentication with Duke DS
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.TextField(unique=True, blank=False, null=False) # Opaque here, but JWT in practice


class DukeDSSettings(models.Model):
    """
    Singleton that contains settings for DukeDS integration 
    """
    url = models.URLField(null=False, blank=False)
    portal_root = models.URLField(null=False, blank=False)
    openid_provider_id = models.CharField(max_length=64, null=False, blank=False)
