import requests
from django.core.management.base import BaseCommand
from league.models import Player, PlayerPosition

# DIRECT AKAMAI IP FOR NHL API (bypasses DNS)
AKAMAI_IP = "23.217.138.110"
BASE_URL = f"https://{AKAMAI_IP}/api/v1"

# Always spoof the Host header so Akamai knows what site we want
HEADERS = {
    "Host": "statsapi.web.nhl.com",
    "User-Agent": "Mozilla/5.0"
}


class Command(BaseCommand):
    help = "Imports NHL players using direct IP bypass (DNS not required)."

    def get(self, endpoint):
        """Wrapper around requests.get using IP + Host header."""
        url = BASE_URL + endpoint
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        return response.json()

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching NHL teams (IP bypass)...")

        teams_data = self.get("/teams")
        teams = teams_data.get("teams", [])

        count = 0

        for team in teams:
            team_id = team["id"]
            team_name = team["name"]

            self.stdout.write(f"Processing {team_name}...")

            roster_data = self.get(f"/teams/{team_id}/roster")
            roster = roster_data.get("roster", [])

            for entry in roster:
                player_id = entry["person"]["id"]

                # Player details lookup
                pdata = self.get(f"/people/{player_id}")["people"][0]

                position_code = pdata["primaryPosition"]["code"]

                # Ensure PlayerPosition exists
                pos_obj, _ = PlayerPosition.objects.get_or_create(code=position_code)

                # Save/update the player
                Player.objects.update_or_create(
                    nhl_id=player_id,
                    defaults={
                        "first_name": pdata["firstName"],
                        "last_name": pdata["lastName"],
                        "full_name": pdata["fullName"],
                        "position": pos_obj,
                        "shoots": pdata.get("shootsCatches"),
                        "number": pdata.get("primaryNumber"),
                        "headshot": (
                            f"https://cms.nhl.bamgrid.com/images/headshots/current/"
                            f"168x168/{player_id}.jpg"
                        ),
                    }
                )

                count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {count} players via IP bypass."))
