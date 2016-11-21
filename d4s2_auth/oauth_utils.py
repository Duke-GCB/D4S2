from __future__ import print_function
import requests
from requests_oauthlib import OAuth2Session
from .models import OAuthService, OAuthToken
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from logging import Logger

USERNAME_KEY = 'sub'

def make_oauth(oauth_service):
    return OAuth2Session(oauth_service.client_id,
                         redirect_uri=oauth_service.redirect_uri,
                         scope=oauth_service.scope.split())

def authorization_url(oauth_service):
    oauth = make_oauth(oauth_service)
    return oauth.authorization_url(oauth_service.authorization_uri) # url, state


def get_token_dict(oauth_service, code):
    """
    :param oauth_service: An OAuthService model object
    :param code: the auth code
    :return: A token dictionary, containing access_token and refresh_token
    """
    oauth = make_oauth(oauth_service)
    # Use code or authorization_response
    if oauth_service.token_uri[-1] == '/':
        Logger.warn("Token URI '{}' ends with '/', this has been a problem with Duke OAuth".format(oauth_service.token_uri))

    token = oauth.fetch_token(oauth_service.token_uri,
                              code=code,
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


class OAuthException(BaseException):
    pass


def save_token(oauth_service, token_dict, user):
    # TODO: Replace token if exists for user/service
    token = OAuthToken(user=user, service=oauth_service)
    token.token_dict = token_dict
    token.save()


def user_from_token(oauth_service, token_dict):
    resource = get_resource(oauth_service, token_dict)
    if USERNAME_KEY not in resource:
        raise OAuthException('Did not find username key in resource: {}'.format(resource),)
    user, created = get_user_model().objects.get_or_create(username=resource.get(USERNAME_KEY))
    if created:
        # TODO: Fetch user details
        pass
    return user


def extract_code(url):
    import urlparse
    parsed = urlparse.urlparse(url)
    query = urlparse.parse_qs(parsed.query)
    return query.get('code')[0]


def main():
    duke_service = OAuthService.objects.first()
    auth_url, state = authorization_url(duke_service)
    print('Please go to {} and authorize access'.format(auth_url))
    authorization_response = raw_input('Enter the full callback URL: ')
    # Probably need the state?
    code = extract_code(authorization_response)
    token = get_token_dict(duke_service, code)
    print('Token: {}'.format(token))
    resource = get_resource(duke_service, token)
    print(resource)

if __name__ == '__main__':
    main()

