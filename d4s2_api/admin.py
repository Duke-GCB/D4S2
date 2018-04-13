from django.contrib import admin
from d4s2_api.models import *
from gcb_web_auth.models import DDSEndpoint, DDSUserCredential
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(EmailTemplate)


class ShareAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(Share, ShareAdmin)


class DeliveryAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(Delivery, DeliveryAdmin)
admin.site.register(DeliveryShareUser)
admin.site.register(DDSEndpoint)
admin.site.register(DDSUserCredential)
admin.site.register(EmailTemplateSet)
admin.site.register(UserEmailTemplateSet)
