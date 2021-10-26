from django.contrib import admin, messages
from d4s2_api.models import *
from simple_history.admin import SimpleHistoryAdmin
from switchboard.dds_util import DDSMessageFactory, MessageDirection
from d4s2_api_v1.api import resend_acceptance_email


admin.site.register(EmailTemplate)


class ShareAdmin(SimpleHistoryAdmin):
    pass


admin.site.register(Share, ShareAdmin)


@admin.action(description='Resend accepted email')
def resend_accepted_email(modeladmin, request, queryset):
    for delivery in queryset:
        if delivery.state == State.ACCEPTED:
            resend_acceptance_email(delivery, request.user)
            message = "Accepted email for project {} was sent.".format(delivery.project_name)
            modeladmin.message_user(request, message=message, level=messages.INFO)
        else:
            message = "Project {} is not in accepted state.".format(delivery.project_name)
            modeladmin.message_user(request, message=message, level=messages.ERROR)


class DDSDeliveryAdmin(SimpleHistoryAdmin):
    actions = [resend_accepted_email]

    def has_delete_permission(self, request, obj=None):
        return False


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
