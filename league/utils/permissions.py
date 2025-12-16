from league.models import LeagueRole


def user_has_role(user, league, roles):
    """
    Check whether a user has one of the allowed roles in a league.
    - Supports single role (string) or list of roles.
    - Treats league.commissioner as "COMMISSIONER".
    """
    if not user.is_authenticated:
        return False

    # Normalize roles input
    if isinstance(roles, str):
        roles = [roles]

    # Built-in commissioner counts for "COMMISSIONER"
    if "COMMISSIONER" in roles and league.commissioner == user:
        return True

    # Database roles (CO_COMMISSIONER, MANAGER, etc)
    return LeagueRole.objects.filter(
        league=league,
        user=user,
        role__in=roles
    ).exists()

