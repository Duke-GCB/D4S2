from django.conf.urls import url
from . import views, views_classes
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache


def decorate(view):
    """
    Decorate our views as requied and never_cache
    :param view: The view to decorate
    :return: The view, decorated with login_required and never_cache
    """
    return login_required(never_cache(view))


urlpatterns = [
    url(r'^$', login_required(views_classes.PromptView.as_view()), name='ownership-prompt'),
    url(r'^process/$', decorate(views_classes.ProcessView.as_view()), name='ownership-process'),
    url(r'^decline/$', decorate(views_classes.DeclineView.as_view()), name='ownership-decline'),
    url(r'^accepted/$',decorate(views_classes.AcceptedView.as_view()), name='ownership-accepted'),
    url(r'^declined/$', decorate(views_classes.DeclinedView.as_view()), name='ownership-declined'),
]
