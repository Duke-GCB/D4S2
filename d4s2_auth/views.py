from django.shortcuts import render
from .oauth_utils import *
from .models import OAuthService
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required


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
    user = authenticate(service=service, token_dict=token_dict)
    if user :
        save_token(service, token_dict, user)
        login(request, user)
        return redirect('home')
    else:
        return redirect('login')


def login_page(request):
    return render(request, 'd4s2_auth/login.html')


@login_required
def user_details(request):
    return render(request, 'd4s2_auth/user_details.html', {'user': request.user})
