from django.core.management.base import BaseCommand
from gcb_web_auth.models import DukeDSSettings


class Command(BaseCommand):
    help = 'Create/Replace DukeDSSettings in the database.'

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='DukeDS API url')
        parser.add_argument('portal_root', type=str, help='DukeDS portal url')
        parser.add_argument('openid_provider_id', type=str, help='OpenID provider from DukeDS api/v1/auth_providers')

    def handle(self, *args, **options):
        url = options['url']
        portal_root = options['portal_root']
        openid_provider_id = options['openid_provider_id']
        settings = DukeDSSettings.objects.first()
        if settings:
            settings.url = url
            settings.portal_root = portal_root
            settings.openid_provider_id = openid_provider_id
            settings.save()
        else:
            DukeDSSettings.objects.create(url=url, portal_root=portal_root, openid_provider_id=openid_provider_id)
