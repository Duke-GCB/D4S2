from django.contrib import admin
from handover_api.models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(DukeDSUser)


class DraftAdmin(SimpleHistoryAdmin):
    pass

admin.site.register(Draft, DraftAdmin)


class HandoverAdmin(SimpleHistoryAdmin):
    readonly_fields = ('token',)

admin.site.register(Handover, HandoverAdmin)
