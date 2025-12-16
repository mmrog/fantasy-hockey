import requests
from django.core.management.base import BaseCommand
from league.models import Player, PlayerPosition


def fetch_landing(player_id):
    """Direct call to landing page (nhl_get cannot be used)."""
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


class Command(BaseCommand):
    help = "Import NHL players using the modern NHL API."

    def safe_json(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def handle(self, *args, **kwargs):

        self.stdout.write("Fetching NHL standings...")

        standings = self.safe_json("https://api-web.nhle.com/v1/standings/now")
        teams = standings.get("standings", [])

        imported = 0

        for team in teams:

            team_name = team.get("teamName", {}).get("default", "Unknown")
            team_abbrev = team.get("teamAbbrev", {}).get("default")

            if not team_abbrev:
                continue

            self.stdout.write(f"Fetching roster for: {team_name} ({team_abbrev})")

            roster = self.safe_json(f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current")

            players = (
                roster.get("forwards", [])
                + roster.get("defensemen", [])
                + roster.get("goalies", [])
            )

            for p in players:
                player_id = p.get("id")
                if not player_id:
                    continue

                landing_data = fetch_landing(player_id)

                if not landing_data:
                    self.stdout.write(self.style.WARNING(f"⚠ No landing page for {player_id}, skipping"))
                    continue

                # HERE IS THE FIX — landing_data IS THE PLAYER OBJECT
                info = landing_data

                # Validate real structure
                if "firstName" not in info or "lastName" not in info:
                    self.stdout.write(self.style.WARNING(f"⚠ No player data for {player_id}, skipping"))
                    continue

                first = info["firstName"].get("default", "")
                last = info["lastName"].get("default", "")
                full_name = info.get("fullName", f"{first} {last}".strip())

                pos_code = info.get("positionCode", "UNK")
                pos_obj, _ = PlayerPosition.objects.get_or_create(code=pos_code)

                # Normalize stats
                raw_stats = info.get("seasonTotals", {})

                if isinstance(raw_stats, dict):
                    stats = raw_stats
                elif isinstance(raw_stats, list) and raw_stats and isinstance(raw_stats[0], dict):
                    stats = raw_stats[0]
                else:
                    stats = {}

                games = stats.get("gamesPlayed", 0)
                goals = stats.get("goals", 0)
                assists = stats.get("assists", 0)
                points = stats.get("points", 0)
                shots = stats.get("shots", 0)
                hits = stats.get("hits", 0)

                jersey = info.get("sweaterNumber")
                shoots = info.get("shootsCatches")
                headshot_url = f"https://assets.nhle.com/mugs/nhl/{player_id}.png"

                Player.objects.update_or_create(
                    nhl_id=player_id,
                    defaults={
                        "first_name": first,
                        "last_name": last,
                        "full_name": full_name,
                        "position": pos_obj,
                        "shoots": shoots,
                        "number": jersey,
                        "headshot": headshot_url,
                        "games_played": games,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "shots": shots,
                        "hits": hits,
                    },
                )

                imported += 1

        self.stdout.write(
            self.style.SUCCESS(f"Imported or updated {imported} NHL players successfully.")
        )
