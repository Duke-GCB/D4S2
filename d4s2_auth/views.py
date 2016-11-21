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
    code = request.GET.get('code')
    token_dict = get_token_dict(service, code)
    # Determine identity of the user, using the token
    user = user_from_token(service, token_dict)
    save_token(service, token_dict, user)
    # user = User.objects.get(username=eppn)
    return render(request, 'd4s2_auth/callback.html', {'user': user})

