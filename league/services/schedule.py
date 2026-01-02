# league/services/schedule.py
from __future__ import annotations

from datetime import date as date_type
from typing import List, Optional, Tuple

from django.db import transaction

from league.models import Team
from league.models_matchups import Matchup


@transaction.atomic
def create_daily_matchups(*, league, day: date_type) -> List[Matchup]:
    """
    Pairs teams for one day. If odd number of teams, one team has a BYE (no matchup created).
    Pairing is deterministic (by team id) for now.
    """
    teams = list(Team.objects.filter(league=league).order_by("id"))
    if len(teams) < 2:
        return []

    bye: Optional[Team] = None
    if len(teams) % 2 == 1:
        bye = teams.pop()  # last team gets bye

    pairings: List[Tuple[Team, Team]] = []
    i, j = 0, len(teams) - 1
    while i < j:
        pairings.append((teams[i], teams[j]))
        i += 1
        j -= 1

    created: List[Matchup] = []
    for home, away in pairings:
        m, _ = Matchup.objects.get_or_create(
            league=league,
            date=day,
            home_team=home,
            away_team=away,
            defaults={"processed": False},
        )
        created.append(m)

    return created
