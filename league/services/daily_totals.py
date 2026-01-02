# league/services/daily_totals.py
# FIX: your ScoringCategory model doesn't use "code".
# Make the code-field dynamic (same pattern we used earlier).

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Dict, Iterable, Optional, Protocol, Sequence

from django.db import transaction

from league.models import DailyLineup, DailySlot, ScoringCategory, Team
from league.models_matchups import TeamCategoryTotal


STARTER_EXCLUDE_CODES = {"BN", "IR"}


class StatProvider(Protocol):
    def get_player_category_totals(self, *, player, day: date_type) -> Dict[str, float]: ...


@dataclass(frozen=True)
class ModelFieldStatProvider:
    field_map: Dict[str, str] = None

    def __post_init__(self):
        if self.field_map is None:
            object.__setattr__(
                self,
                "field_map",
                {
                    "G": "goals",
                    "A": "assists",
                    "+/-": "plus_minus",
                    "PIM": "pim",
                    "PPP": "ppp",
                    "SHG": "shg",
                    "GWG": "gwg",
                    "SOG": "shots",
                    "HIT": "hits",
                    "BLK": "blocks",
                    "W": "wins",
                    "GA": "goals_against",
                    "SV": "saves",
                    "SO": "shutouts",
                },
            )

    def get_player_category_totals(self, *, player, day: date_type) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for code, field_name in self.field_map.items():
            val = getattr(player, field_name, 0) or 0
            try:
                totals[code] = float(val)
            except (TypeError, ValueError):
                totals[code] = 0.0
        return totals


def _starter_slots_for_team_day(team: Team, day: date_type) -> Iterable[DailySlot]:
    lineup, _ = DailyLineup.objects.get_or_create(team=team, date=day)
    return (
        DailySlot.objects.filter(lineup=lineup)
        .select_related("player", "slot")
        .exclude(player__isnull=True)
        .exclude(slot__code__in=STARTER_EXCLUDE_CODES)
    )


def _category_code_field() -> str:
    """
    Returns the actual field name used for the category code/key on your ScoringCategory model.
    """
    candidates = ["code", "abbr", "key", "stat_key", "stat", "slug"]
    model_fields = {f.name for f in ScoringCategory._meta.get_fields() if hasattr(f, "name")}
    for c in candidates:
        if c in model_fields:
            return c
    raise AttributeError("ScoringCategory has no recognized code field (expected one of: code/abbr/key/stat_key/stat/slug).")


@transaction.atomic
def compute_team_category_totals_for_day(
    *,
    league,
    day: date_type,
    stat_provider: Optional[StatProvider] = None,
) -> int:
    provider: StatProvider = stat_provider or ModelFieldStatProvider()

    categories = list(ScoringCategory.objects.filter(league=league))
    code_field = _category_code_field()

    cat_codes: Sequence[str] = [getattr(c, code_field) for c in categories if getattr(c, code_field, None)]
    TeamCategoryTotal.objects.filter(league=league, date=day).delete()

    rows_to_create = []

    teams = Team.objects.filter(league=league).order_by("id")
    for team in teams:
        totals_by_code: Dict[str, float] = {code: 0.0 for code in cat_codes}

        for slot in _starter_slots_for_team_day(team, day):
            player_totals = provider.get_player_category_totals(player=slot.player, day=day)
            for code in cat_codes:
                totals_by_code[code] += float(player_totals.get(code, 0.0) or 0.0)

        for cat in categories:
            code = getattr(cat, code_field, None)
            if not code:
                continue
            rows_to_create.append(
                TeamCategoryTotal(
                    league=league,
                    team=team,
                    date=day,
                    category=cat,
                    value=totals_by_code.get(code, 0.0),
                )
            )

    TeamCategoryTotal.objects.bulk_create(rows_to_create)
    return len(rows_to_create)
