from django.shortcuts import render
from .oauth_utils import *
from .models import OAuthService
from d4s2_api.models import User
from django.shortcuts import redirect


def get_service(request):
    # TODO: Return a different service if necessary
    return OAuthService.objects.first()


def authorize(request):
    service = get_service(request)
    auth_url, _ = authorization_url(service)
    return redirect(auth_url)


def authorize_callback(request):
    service = get_service(request)
    # This gets the token dictionary from the callback URL
    token_dict = get_token_dict(service, request.build_absolute_uri())
    # Determine identity of the user, using the token
    resource = get_resource(service, token_dict)
    # extract eppn
    # {u'scope': u'basic', u'eppn': u'dcl9@duke.edu'}
    eppn = resource.get('eppn')
    # TODO: Try to find a user with this username
    # user = User.objects.get(username=eppn)
    return render(request, 'd4s2_auth/callback.html', {'user': eppn})

