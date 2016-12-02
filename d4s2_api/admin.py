from django.contrib import admin
from d4s2_api.models import *
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(DukeDSUser)
admin.site.register(DukeDSProject)
admin.site.register(EmailTemplate)

class ShareAdmin(SimpleHistoryAdmin):
    pass

admin.site.register(Share, ShareAdmin)


class DeliveryAdmin(SimpleHistoryAdmin):
    pass

admin.site.register(Delivery, DeliveryAdmin)
