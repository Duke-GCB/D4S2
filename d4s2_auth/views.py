from django.shortcuts import render
from .oauth_utils import *
from .models import OAuthService, OAuthState
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

def get_service(request):
    # TODO: Return a different service if necessary
    return OAuthService.objects.first()


class StateException(BaseException):
    pass


def push_state(request, state_string, destination_param='next'):
    saved_state = OAuthState.objects.create(state=state_string)
    if destination_param in request.GET:
        saved_state.destination = request.GET[destination_param]
        saved_state.save()
    return saved_state


def pop_state(request):
    if 'state' in request.GET:
        state_string = request.GET['state']
        try:
            state = OAuthState.objects.get(state=state_string)
            # Delete the state
            destination = state.destination
            state.delete()
            return destination
        except ObjectDoesNotExist as e:
            raise StateException('State {} not found'.format(state_string))
    else:
        raise StateException('URL missing state parameter')


def authorize(request):
    service = get_service(request)
    auth_url, state_string = authorization_url(service)
    # Save the state with the next parameter if provided
    push_state(request, state_string)
    return redirect(auth_url)


def authorize_callback(request):
    destination = pop_state(request)
    service = get_service(request)
    # This gets the token dictionary from the callback URL
    token_dict = get_token_dict(service, request.build_absolute_uri())
    # Determine identity of the user, using the token
    user = authenticate(service=service, token_dict=token_dict)
    if user:
        save_token(service, token_dict, user)
        login(request, user)
        if not destination:
            return redirect('home')
        else:
            return redirect(destination)
    else:
        return redirect('login')


def login_page(request):
    return render(request, 'd4s2_auth/login.html')


@login_required
def user_details(request):
    return render(request, 'd4s2_auth/user_details.html', {'user': request.user})
