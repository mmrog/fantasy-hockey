# league/management/commands/aggregate_day.py
from datetime import date as date_type

from django.core.management.base import BaseCommand
from django.utils import timezone

from league.models import League
from league.services.daily_totals import compute_team_category_totals_for_day


class Command(BaseCommand):
    help = "Aggregate starter lineups into TeamCategoryTotal for a given league + date."

    def add_arguments(self, parser):
        parser.add_argument("--league_id", type=int, required=True)
        parser.add_argument("--date", type=str, default=None)  # YYYY-MM-DD

    def handle(self, *args, **options):
        league = League.objects.get(id=options["league_id"])
        day = date_type.fromisoformat(options["date"]) if options["date"] else timezone.localdate()

        written = compute_team_category_totals_for_day(league=league, day=day)
        self.stdout.write(self.style.SUCCESS(f"Aggregated {written} TeamCategoryTotal rows for {league} on {day}."))
