from ddsc.sdk.client import Client
from gcb_web_auth.models import DDSUserCredential
from gcb_web_auth.utils import get_dds_config_for_credentials, get_dds_token, make_auth_config


def make_client(user):
    try:
        dds_credential = DDSUserCredential.objects.get(user=user)
        config = get_dds_config_for_credentials(dds_credential)
    except DDSUserCredential.DoesNotExist:
        # No DDSUserCredential configured for this user, fall back to OAuth
        # May raise an OAuthConfigurationException
        dds_token = get_dds_token(user)
        config = make_auth_config(dds_token.key)
    client = Client(config=config)
    return client
