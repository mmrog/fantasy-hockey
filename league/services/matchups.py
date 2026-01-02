# league/services/matchups.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from django.db import transaction

from league.models import ScoringCategory
from league.models_matchups import Matchup, MatchupCategoryResult, TeamCategoryTotal


@dataclass(frozen=True)
class CategoryCompareResult:
    category_id: int
    category_code: str
    home_value: float
    away_value: float
    winner: str  # "HOME" | "AWAY" | "TIE"


def _winner_for_category(*, lower_is_better: bool, home_value: float, away_value: float) -> str:
    if home_value == away_value:
        return "TIE"
    if lower_is_better:
        return "HOME" if home_value < away_value else "AWAY"
    return "HOME" if home_value > away_value else "AWAY"


def compare_daily_categories(*, league, home_totals_by_code: Dict[str, float], away_totals_by_code: Dict[str, float]):
    categories = ScoringCategory.objects.filter(league=league).order_by("id")

    results_by_code: Dict[str, CategoryCompareResult] = {}
    home_cats = away_cats = ties = 0

    for cat in categories:
        code = getattr(cat, "code", None)
        if not code:
            continue

        home_val = float(home_totals_by_code.get(code, 0))
        away_val = float(away_totals_by_code.get(code, 0))

        lower_is_better = bool(getattr(cat, "lower_is_better", False))
        winner = _winner_for_category(lower_is_better=lower_is_better, home_value=home_val, away_value=away_val)

        if winner == "HOME":
            home_cats += 1
        elif winner == "AWAY":
            away_cats += 1
        else:
            ties += 1

        results_by_code[code] = CategoryCompareResult(
            category_id=cat.id,
            category_code=code,
            home_value=home_val,
            away_value=away_val,
            winner=winner,
        )

    summary = {"home_cats": home_cats, "away_cats": away_cats, "ties": ties}
    return results_by_code, summary


@transaction.atomic
def compute_and_store_matchup_results(*, matchup: Matchup) -> Dict[str, int]:
    """
    Pulls TeamCategoryTotal rows for the matchup date and stores MatchupCategoryResult rows.
    Mark matchup.processed = True.
    """
    def totals_for_team(team_id: int) -> Dict[str, float]:
        rows = (
            TeamCategoryTotal.objects
            .filter(league=matchup.league, team_id=team_id, date=matchup.date)
            .select_related("category")
        )
        return {r.category.code: float(r.value) for r in rows if getattr(r.category, "code", None)}

    home_totals = totals_for_team(matchup.home_team_id)
    away_totals = totals_for_team(matchup.away_team_id)

    results_by_code, summary = compare_daily_categories(
        league=matchup.league,
        home_totals_by_code=home_totals,
        away_totals_by_code=away_totals,
    )

    MatchupCategoryResult.objects.filter(matchup=matchup).delete()

    cats = {c.code: c for c in ScoringCategory.objects.filter(league=matchup.league)}

    MatchupCategoryResult.objects.bulk_create(
        [
            MatchupCategoryResult(
                matchup=matchup,
                category=cats[code],
                home_value=r.home_value,
                away_value=r.away_value,
                winner=r.winner,
            )
            for code, r in results_by_code.items()
            if code in cats
        ]
    )

    matchup.processed = True
    matchup.save(update_fields=["processed"])

    return summary
