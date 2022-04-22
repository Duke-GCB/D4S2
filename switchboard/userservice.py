from django.conf import settings
from rest_framework.exceptions import APIException, NotFound
import requests
import re
from d4s2_api.utils import get_netid_from_user


class UserServiceException(APIException):
    pass


class User(object):
    def __init__(self, person_dict):
        given_name = person_dict['givenName']
        sn = person_dict['sn']
        netid = person_dict['netid']
        display_name = person_dict['display_name']
        email = person_dict.get('emails', [None])[0]
        if not email:
            email = create_email_from_netid(netid)
        self.id = netid
        self.username = netid
        self.full_name = display_name
        self.first_name = given_name
        self.last_name = sn
        self.email = email


def _make_directory_service_url(url_suffix):
    if not settings.DIRECTORY_SERVICE_URL:
        raise UserServiceException("Error: Missing DIRECTORY_SERVICE_URL configuration.")
    return "{}{}".format(settings.DIRECTORY_SERVICE_URL, url_suffix)


def _get_directory_service_access_token():
    if not settings.DIRECTORY_SERVICE_TOKEN:
        raise UserServiceException("Error: Missing DIRECTORY_SERVICE_TOKEN configuration.")
    return settings.DIRECTORY_SERVICE_TOKEN


def _get_json_response(url, **kwargs):
    data = {"access_token": _get_directory_service_access_token()}
    data.update(kwargs)
    response = requests.get(url, data=data)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        try:
            raise UserServiceException(response.json().get("error"))
        except ValueError:
            raise UserServiceException(e)


def get_users_for_query(q):
    result = []
    url = _make_directory_service_url("/ldap/people")
    for person_dict in _get_json_response(url, q=q):
        # filter out users without a netid
        if "netid" in person_dict:
            result.append(User(person_dict))
    return result


def get_user_for_netid(netid):
    url = _make_directory_service_url("/ldap/people/netid/{}".format(netid))
    resp = _get_json_response(url)
    if len(resp) != 1:
        raise NotFound("No user found for netid {}".format(netid))
    return User(resp[0])


def create_email_from_netid(netid):
    # email addresses can be created by adding a host to a username for users who
    # have their email addresses hidden in the DukeDS affiliates API
    if settings.USERNAME_EMAIL_HOST:
        return '{}@{}'.format(netid, settings.USERNAME_EMAIL_HOST)
    return None
