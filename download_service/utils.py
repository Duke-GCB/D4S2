from ddsc.sdk.client import Client
from ddsc.core.ddsapi import OAuthDataServiceAuth
from ddsc.config import Config
from gcb_web_auth.models import DDSUserCredential
from gcb_web_auth.utils import get_dds_config_for_credentials, get_oauth_token, get_default_dds_endpoint


def make_client(user):
    try:
        dds_credential = DDSUserCredential.objects.get(user=user, token='blah')
        config = get_dds_config_for_credentials(dds_credential)
        return Client(config=config)
    except DDSUserCredential.DoesNotExist:
        # No DDSUserCredential configured for this user, fall back to OAuth
        # May raise an OAuthConfigurationException
        endpoint = get_default_dds_endpoint()
        config = Config()
        config.update_properties({
            Config.URL: endpoint.api_root,
        })
        authentication_service_id = endpoint.openid_provider_service_id

        def create_data_service_auth(config, set_status_msg=print):
            return MyOAuthDataServiceAuth(user, authentication_service_id, config, set_status_msg=set_status_msg)

        return Client(config=config, create_data_service_auth=create_data_service_auth)


class MyOAuthDataServiceAuth(OAuthDataServiceAuth):
    def __init__(self, user, authentication_service_id, config, set_status_msg=print):
        super().__init__(config, set_status_msg)
        self._auth = None
        self.user = user
        self.authentication_service_id = authentication_service_id

    def create_oauth_access_token(self):
        oauth_token = get_oauth_token(self.user)
        return oauth_token.token_dict.get('access_token')

    def get_authentication_service_id(self):
        endpoint = get_default_dds_endpoint()
        return endpoint.openid_provider_service_id
