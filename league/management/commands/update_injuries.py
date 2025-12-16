import requests
from django.core.management.base import BaseCommand
from league.models import Player

NHL_TEAMS_URL = "https://statsapi.web.nhl.com/api/v1/teams?expand=team.roster"


class Command(BaseCommand):
    help = "Updates injury status for all NHL players using the public NHL API"

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching NHL roster data...")

        try:
            data = requests.get(NHL_TEAMS_URL, timeout=10).json()
        except:
            self.stdout.write(self.style.ERROR("Failed to connect to NHL API"))
            return

        updated_count = 0
        cleared_count = 0

        for team in data.get("teams", []):
            roster = team.get("roster", {}).get("roster", [])
            for player in roster:
                person = player["person"]
                player_id = person["id"]
                status = player.get("rosterStatus", "N")  # N = Normal

                try:
                    db_player = Player.objects.get(nhl_id=player_id)
                except Player.DoesNotExist:
                    continue

                # Injury logic
                if status in ("I", "IR"):
                    if not db_player.injured:
                        db_player.injured = True
                        db_player.injury_note = status
                        db_player.save(update_fields=["injured", "injury_note"])
                        updated_count += 1

                else:
                    # If previously marked injured and now healthy
                    if db_player.injured:
                        db_player.injured = False
                        db_player.injury_note = None
                        db_player.save(update_fields=["injured", "injury_note"])
                        cleared_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Injury update complete. {updated_count} marked injured, {cleared_count} cleared."
        ))
