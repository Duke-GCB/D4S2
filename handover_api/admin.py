from django.contrib import admin
from handover_api.models import *

admin.site.register(DukeDSUser)
admin.site.register(Draft)


class HandoverAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)

admin.site.register(Handover, HandoverAdmin)
