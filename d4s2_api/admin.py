from django.contrib import admin
from d4s2_api.models import *
from gcb_web_auth.models import DDSEndpoint, DDSUserCredential
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(EmailTemplate)


class ShareAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(Share, ShareAdmin)


class DDSDeliveryAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(DDSDelivery, DDSDeliveryAdmin)
admin.site.register(DDSDeliveryError)
admin.site.register(DDSDeliveryShareUser)
admin.site.register(DDSEndpoint)
admin.site.register(DDSUserCredential)
admin.site.register(EmailTemplateSet)
admin.site.register(UserEmailTemplateSet)
admin.site.register(S3Endpoint)
admin.site.register(S3User)
admin.site.register(S3UserCredential)
admin.site.register(S3Bucket)


class S3DeliveryAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(S3Delivery, S3DeliveryAdmin)
admin.site.register(S3DeliveryError)
admin.site.register(S3ObjectManifest)
