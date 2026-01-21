# league/utils/decorators.py
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404

from league.models import League, LeagueRole


def commissioner_required(view_func):
    """
    Allows League commissioner OR co-commissioner.
    Expects the view to have league_id in kwargs or as 2nd positional arg.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        league_id = kwargs.get("league_id")
        if league_id is None and len(args) >= 1:
            # common signature: (request, league_id, ...)
            league_id = args[0]

        league = get_object_or_404(League, id=league_id)

        if not request.user.is_authenticated:
            return HttpResponseForbidden("Login required.")

        is_commish = league.commissioner_id == request.user.id
        is_co_commish = LeagueRole.objects.filter(
            league=league,
            user=request.user,
            role__in=["COMMISSIONER", "CO_COMMISSIONER"],
        ).exists()

        if not (is_commish or is_co_commish):
            return HttpResponseForbidden("Commissioner access only.")

        return view_func(request, *args, **kwargs)

    return _wrapped
