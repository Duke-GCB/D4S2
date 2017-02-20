from django.contrib import admin
from d4s2_auth.models import OAuthService, OAuthToken, DukeDSAPIToken

# Register your models here.
admin.site.register(OAuthService)
admin.site.register(OAuthToken)
admin.site.register(DukeDSAPIToken)