from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from league.models import League
from .permissions import user_has_role


def role_required(*required_roles):
    """
    Example:
        @role_required("COMMISSIONER")
        @role_required("COMMISSIONER", "CO_COMMISSIONER")

    Requires the view to accept a league_id in the URL pattern.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, league_id, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Not logged in.")

            league = get_object_or_404(League, id=league_id)

            if not user_has_role(request.user, league, list(required_roles)):
                return HttpResponseForbidden("Insufficient permissions.")

            return view_func(request, league_id, *args, **kwargs)
        return wrapper
    return decorator


def commissioner_required(view_func):
    """
    Commissioner-only views.
    Allows COMMISSIONER and CO_COMMISSIONER.
    """
    @login_required
    @wraps(view_func)
    def wrapped(request, league_id, *args, **kwargs):
        return role_required("COMMISSIONER", "CO_COMMISSIONER")(view_func)(
            request, league_id, *args, **kwargs
        )
    return wrapped
