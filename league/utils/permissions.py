# league/utils/permissions.py

from league.models import LeagueRole


def user_has_role(user, league, roles):
    if not user.is_authenticated:
        return False

    if isinstance(roles, str):
        roles = [roles]

    # Built-in league commissioner counts as "COMMISSIONER"
    if "COMMISSIONER" in roles and league.commissioner == user:
        return True

    return LeagueRole.objects.filter(
        league=league,
        user=user,
        role__in=roles
    ).exists()
