from django.contrib import admin
from gcb_web_auth.models import OAuthService, OAuthToken, DukeDSAPIToken

# Register your models here.
admin.site.register(OAuthService)
admin.site.register(OAuthToken)
admin.site.register(DukeDSAPIToken)
