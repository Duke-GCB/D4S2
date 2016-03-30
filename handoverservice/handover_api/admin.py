from django.contrib import admin

from handover_api.models import *

admin.site.register(User)
admin.site.register(Handover)
admin.site.register(Draft)