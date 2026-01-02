# league/services/matchup_persist.py
from __future__ import annotations

from typing import Dict

from django.db import transaction

from league.models_matchups import Matchup, MatchupCategoryResult
from league.services.matchups import compare_daily_categories, standings_points_from_summary


@transaction.atomic
def compute_and_store_matchup_results(
    *,
    matchup: Matchup,
    home_totals_by_code: Dict[str, float],
    away_totals_by_code: Dict[str, float],
) -> Dict[str, int]:
    """
    Computes per-category winners and saves rows into MatchupCategoryResult.
    Returns summary dict: {"home_cats": X, "away_cats": Y, "ties": Z}
    """
    results_by_code, summary = compare_daily_categories(
        league=matchup.league,
        home_totals_by_code=home_totals_by_code,
        away_totals_by_code=away_totals_by_code,
    )

    # Clear + re-create is simplest for now (idempotent per day)
    MatchupCategoryResult.objects.filter(matchup=matchup).delete()

    # Lookup categories once by code
    categories = {c.code: c for c in matchup.league.scoringcategory_set.all()}

    for code, r in results_by_code.items():
        cat = categories.get(code)
        if not cat:
            continue
        MatchupCategoryResult.objects.create(
            matchup=matchup,
            category=cat,
            home_value=r.home_value,
            away_value=r.away_value,
            winner=r.winner,
        )

    return summary
