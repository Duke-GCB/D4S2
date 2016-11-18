from __future__ import print_function
import requests
from requests_oauthlib import OAuth2Session
from models import OAuthService


def make_oauth(oauth_service):
    return OAuth2Session(oauth_service.client_id,
                         redirect_uri=oauth_service.redirect_uri,
                         scope=oauth_service.scope.split())

def authorization_url(oauth_service):
    oauth = make_oauth(oauth_service)
    return oauth.authorization_url(oauth_service.authorization_uri) # url, state


def get_token_dict(oauth_service, authorization_response):
    """
    :param oauth_service: An OAuthService model object
    :param authorization_response: the auth response redirect URI
    :return: A token dictionary, containing access_token and refresh_token
    """
    oauth = make_oauth(oauth_service)
    # Use code or authorization_response
    token = oauth.fetch_token(oauth_service.token_uri,
                              authorization_response=authorization_response,
                              client_secret=oauth_service.client_secret)
    return token


def get_resource(oauth_service, token_dict):
    """
    :param oauth_service: An OAuthService model object
    :param token_dict: a dict containing the access_token
    :return:
    """
    # Only post the access token_dict
    post_data = dict((k, token_dict[k]) for k in ('access_token',))
    response = requests.post(oauth_service.resource_uri, post_data)
    response.raise_for_status()
    return response.json()


def main():
    duke_service = OAuthService.objects.first()
    auth_url, state = authorization_url(duke_service)
    print('Please go to {} and authorize access'.format(auth_url))
    authorization_response = raw_input('Enter the full callback URL: ')
    # Probably need the state?
    token = get_token_dict(duke_service, authorization_response)
    print('Token: {}'.format(token))
    resource = get_resource(duke_service, token)
    print(resource)

if __name__ == '__main__':
    main()

