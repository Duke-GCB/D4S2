from __future__ import unicode_literals
from django.db import models

class OAuthService(models.Model):
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    client_id = models.CharField(max_length=64, null=False, blank=False)
    client_secret = models.CharField(max_length=64, null=False, blank=False)
    authorization_uri = models.URLField(null=False, blank=False)
    token_uri = models.URLField(null=False, blank=False)
    resource_uri = models.URLField(null=False, blank=False)
    redirect_uri = models.URLField(null=False, blank=False)
    scope = models.CharField(max_length=64, null=False, blank=False)

    def __unicode__(self):
        return 'OAuth Service {}, Auth URL: {}'.format(self.name, self.authorization_uri)
