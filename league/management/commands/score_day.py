# league/management/commands/score_day.py
# UPDATED: now runs aggregation first, then computes matchup results.

from datetime import date as date_type

from django.core.management.base import BaseCommand
from django.utils import timezone

from league.models import League
from league.models_matchups import Matchup
from league.services.daily_totals import compute_team_category_totals_for_day
from league.services.matchups import compute_and_store_matchup_results
from league.services.schedule import create_daily_matchups


class Command(BaseCommand):
    help = "Aggregate totals, create daily matchups (if missing), then compute/store category results."

    def add_arguments(self, parser):
        parser.add_argument("--league_id", type=int, required=True)
        parser.add_argument("--date", type=str, default=None)  # YYYY-MM-DD

    def handle(self, *args, **options):
        league = League.objects.get(id=options["league_id"])

        if options["date"]:
            day = date_type.fromisoformat(options["date"])
        else:
            day = timezone.localdate()

        # 1) Aggregate starter lineup stats -> TeamCategoryTotal
        written = compute_team_category_totals_for_day(league=league, day=day)
        self.stdout.write(f"Aggregated {written} TeamCategoryTotal rows for {league} on {day}.")

        # 2) Ensure matchups exist for the day
        created = create_daily_matchups(league=league, day=day)
        self.stdout.write(f"Ensured matchups for {day}. (created/ensured: {len(created)})")

        # 3) Score matchups (category vs category)
        matchups = Matchup.objects.filter(league=league, date=day).select_related("home_team", "away_team")
        for m in matchups:
            summary = compute_and_store_matchup_results(matchup=m)
            self.stdout.write(f"{m}: {summary}")

        self.stdout.write(self.style.SUCCESS("Done."))
