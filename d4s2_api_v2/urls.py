from django.conf.urls import url, include
from rest_framework import routers
from d4s2_api_v2 import api

router = routers.DefaultRouter()
router.register(r'deliveries', api.DeliveryViewSet, 'v2-delivery')
router.register(r'duke-ds-users', api.DDSUsersViewSet, 'v2-dukedsuser')
router.register(r'duke-ds-projects', api.DDSProjectsViewSet, 'v2-dukedsproject')
router.register(r'duke-ds-project-transfers', api.DDSProjectTransfersViewSet, 'v2-dukedsprojecttransfer')
router.register(r'users', api.UserViewSet, 'v2-user')
router.register(r's3-endpoints', api.S3EndpointViewSet, 'v2-s3endpoint')
router.register(r's3-users', api.S3UserViewSet, 'v2-s3user')
router.register(r's3-buckets', api.S3BucketViewSet, 'v2-s3bucket')
router.register(r's3-deliveries', api.S3DeliveryViewSet, 'v2-s3delivery')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'delivery-preview', api.DeliveryPreviewView.as_view(), name='v2-delivery_preview')
]
