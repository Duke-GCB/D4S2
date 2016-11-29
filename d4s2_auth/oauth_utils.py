from __future__ import print_function
import requests
from requests_oauthlib import OAuth2Session
from .models import OAuthService, OAuthToken
import logging

logger = logging.getLogger(__name__)


def make_oauth_session(oauth_service):
    return OAuth2Session(oauth_service.client_id,
                         redirect_uri=oauth_service.redirect_uri,
                         scope=oauth_service.scope.split())


def make_refreshing_oauth_session(oauth_service, token, user):
    extra = { # Extra arguments required by refresh
        'client_id': oauth_service.client_id,
        'client_secret': oauth_service.client_secret,
    }

    def token_saver(updated_token):
        save_token(oauth_service, updated_token, user)

    client = OAuth2Session(client_id=oauth_service.client_id,
                           token=token.token_dict,
                           auto_refresh_kwargs=extra,
                           auto_refresh_url=oauth_service.token_uri,
                           token_updater=token_saver
                           )
    return client


def authorization_url(oauth_service):
    oauth = make_oauth_session(oauth_service)
    return oauth.authorization_url(oauth_service.authorization_uri) # url, state


def get_token_dict(oauth_service, authorization_response):
    """
    :param oauth_service: An OAuthService model object
    :param authorization_response: the full URL containing code and state parameters
    :return: A token dictionary, containing access_token and refresh_token
    """
    oauth = make_oauth_session(oauth_service)
    # Use code or authorization_response
    if oauth_service.token_uri[-1] == '/':
        logger.warn("Token URI '{}' ends with '/', this has been a problem with Duke OAuth".format(oauth_service.token_uri))

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
    session = make_oauth_session(oauth_service)
    session.token = token_dict
    response = session.post(oauth_service.resource_uri)
    try:
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        raise OAuthException(e)


class OAuthException(BaseException):
    pass


def save_token(oauth_service, token_dict, user):
    token, created = OAuthToken.objects.get_or_create(user=user,
                                                      service=oauth_service)
    # If a token already existed we must revoke the old one
    if not created:
        try:
            revoke_token(token)
        except OAuthException as e:
            logger.warn('Unable to revoke token, proceeding to save: {}'.format(e))
        token.token_dict = {}
        token.save()
    # Either way, save the current token
    token.token_dict = token_dict
    token.save()
    return token


def revoke_token(token):
    """
    Revokes a token using it's service's revoke_uri and the refresh_token
    :param token: an OAuthToken object
    :return: JSON response of the revoke status
    """
    service = token.service
    auth = (service.client_id, service.client_secret,)
    # Revoking the refresh token will revoke its parents too
    data = {'token': token.token_dict.get('refresh_token')}
    response = requests.post(service.revoke_uri, auth=auth, data=data)
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise OAuthException(e)


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

