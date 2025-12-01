from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from league.models import League, LeagueRole


def role_required(required_role):
    """
    Decorator for league-specific role checking.
    Use as: @role_required("COMMISSIONER")
    Requires the view to have a league_id in the URL.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, league_id, *args, **kwargs):

            league = get_object_or_404(League, id=league_id)

            # Check if the user has the required role in this league
            role = LeagueRole.objects.filter(
                league=league,
                user=request.user,
                role=required_role
            ).first()

            if not role:
                return HttpResponseForbidden("Insufficient permissions.")

            return view_func(request, league_id, *args, **kwargs)

        return wrapper

    return decorator
