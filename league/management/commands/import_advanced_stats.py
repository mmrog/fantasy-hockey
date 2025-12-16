import requests
from django.core.management.base import BaseCommand
from league.models import Player, PlayerAdvancedStats

ADVANCED_ENDPOINT = (
    "https://statsapi.web.nhl.com/api/v1/people/{player_id}/stats"
    "?stats=statsSingleSeasonAdvanced"
)

class Command(BaseCommand):
    help = "Import advanced NHL stats (xG, CF%, HD metrics) for all players."

    def fetch_advanced(self, player_id):
        url = ADVANCED_ENDPOINT.format(player_id=player_id)
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching advanced stats...")

        total = 0
        updated = 0

        for player in Player.objects.all():
            total += 1

            data = self.fetch_advanced(player.nhl_id)
            if not data:
                self.stdout.write(
                    self.style.WARNING(f"Failed advanced stats for {player.full_name}")
                )
                continue

            stats_list = (
                data.get("stats", [{}])[0]
                .get("splits", [])
            )

            if not stats_list:
                self.stdout.write(
                    self.style.WARNING(f"No advanced stats for {player.full_name}")
                )
                continue

            stat = stats_list[0].get("stat", {})

            adv, _ = PlayerAdvancedStats.objects.update_or_create(
                player=player,
                defaults={
                    "corsi_for": stat.get("corsiFor", 0),
                    "corsi_against": stat.get("corsiAgainst", 0),
                    "corsi_pct": stat.get("corsiPercentage", 0),

                    "fenwick_for": stat.get("fenwickFor", 0),
                    "fenwick_against": stat.get("fenwickAgainst", 0),
                    "fenwick_pct": stat.get("fenwickPercentage", 0),

                    "xg": stat.get("expectedGoals", 0),
                    "ixg": stat.get("individualExpectedGoals", 0),
                    "xga": stat.get("expectedGoalsAgainst", 0),
                    "xgf_pct": stat.get("expectedGoalsPercentage", 0),

                    "hdcf": stat.get("highDangerCorsiFor", 0),
                    "hdca": stat.get("highDangerCorsiAgainst", 0),
                    "hdcf_pct": stat.get("highDangerCorsiPercentage", 0),

                    "points_per_60": stat.get("pointsPer60", 0),
                    "goals_per_60": stat.get("goalsPer60", 0),
                    "assists_per_60": stat.get("assistsPer60", 0),
                }
            )

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated advanced stats for {updated}/{total} players."
            )
        )
