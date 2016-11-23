from django.contrib import admin
from d4s2_auth.models import OAuthService, OAuthToken

# Register your models here.
admin.site.register(OAuthService)
admin.site.register(OAuthToken)