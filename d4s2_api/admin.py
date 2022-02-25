from django.contrib import admin
from d4s2_api.models import *
from simple_history.admin import SimpleHistoryAdmin
from switchboard.azure_util import TransferFunctions

admin.site.register(EmailTemplate)


class ShareAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(Share, ShareAdmin)


class DDSDeliveryAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(DDSDelivery, DDSDeliveryAdmin)
admin.site.register(DDSDeliveryError)
admin.site.register(DDSDeliveryShareUser)
admin.site.register(EmailTemplateSet)
admin.site.register(EmailTemplateType)
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

def restart_transfer(modeladmin, request, queryset):
    for delivery in queryset:
        TransferFunctions.restart_transfer(delivery.id)


class AzDeliveryAdmin(SimpleHistoryAdmin):
    actions = [restart_transfer]


admin.site.register(AzDelivery, AzDeliveryAdmin)
admin.site.register(AzContainerPath)
admin.site.register(AzObjectManifest)
admin.site.register(AzDeliveryError)
admin.site.register(AzStorageConfig)
