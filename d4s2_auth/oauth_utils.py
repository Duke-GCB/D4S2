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


def get_token_dict(oauth_service, authorization_response):
    """
    :param oauth_service: An OAuthService model object
    :param authorization_response: the full URL containing code and state parameters
    :return: A token dictionary, containing access_token and refresh_token
    """
    oauth = make_oauth(oauth_service)
    # Use code or authorization_response
    if oauth_service.token_uri[-1] == '/':
        Logger.warn("Token URI '{}' ends with '/', this has been a problem with Duke OAuth".format(oauth_service.token_uri))

    token = oauth.fetch_token(oauth_service.token_uri,
                              authorization_response=authorization_response,
                              client_secret=oauth_service.client_secret)
    return token


def get_user_details(oauth_service, token_dict):
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
    user_details = get_user_details(oauth_service, token_dict)
    if USERNAME_KEY not in user_details:
        raise OAuthException('Did not find username key in resource: {}'.format(user_details),)
    user, created = get_user_model().objects.get_or_create(username=user_details.get(USERNAME_KEY))
    if created:
        # TODO: Fetch user details
        pass
    return user


def main():
    duke_service = OAuthService.objects.first()
    auth_url, state = authorization_url(duke_service)
    print('Please go to {} and authorize access'.format(auth_url))
    authorization_response = raw_input('Enter the full callback URL: ')
    token = get_token_dict(duke_service, authorization_response)
    print('Token: {}'.format(token))
    user_details = get_user_details(duke_service, token)
    print(user_details)

if __name__ == '__main__':
    main()

