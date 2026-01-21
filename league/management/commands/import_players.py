# league/management/commands/import_players.py
# ✅ UPDATED: adds ADP support (optional CSV) + keeps your NHL import intact
#
# HOW IT WORKS
# 1) Imports/updates NHL players as before
# 2) If you pass --adp-csv=/path/to/adp.csv it will apply ADP values by name (and optional team)
#
# CSV FORMAT (recommended headers):
# full_name,adp
# OR:
# full_name,team,adp   (team = 3-letter abbr like WPG)
#
# EXAMPLES:
# python manage.py import_players
# python manage.py import_players --adp-csv "C:\Users\you\Downloads\adp.csv"

import csv
import requests
from django.core.management.base import BaseCommand


def fetch_landing(player_id: int):
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


class Command(BaseCommand):
    help = "Import NHL players using the modern NHL API (optionally apply ADP from a CSV)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--adp-csv",
            dest="adp_csv",
            default=None,
            help="Optional path to a CSV containing ADP data (headers: full_name,adp OR full_name,team,adp).",
        )

    def safe_json(self, url: str):
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def _apply_adp_csv(self, Player, path: str):
        self.stdout.write(f"Applying ADP from CSV: {path}")

        applied = 0
        missing = 0
        bad = 0

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers = [h.lower().strip() for h in (reader.fieldnames or [])]

            has_team = "team" in headers or "nhl_team_abbr" in headers
            name_key = "full_name" if "full_name" in headers else ("name" if "name" in headers else None)
            adp_key = "adp" if "adp" in headers else None
            team_key = "team" if "team" in headers else ("nhl_team_abbr" if "nhl_team_abbr" in headers else None)

            if not name_key or not adp_key:
                raise ValueError("CSV must include headers full_name (or name) and adp.")

            for row in reader:
                full_name = (row.get(name_key) or "").strip()
                if not full_name:
                    bad += 1
                    continue

                raw_adp = (row.get(adp_key) or "").strip()
                try:
                    adp_val = float(raw_adp)
                except Exception:
                    bad += 1
                    continue

                qs = Player.objects.filter(full_name__iexact=full_name)

                if has_team and team_key:
                    team = (row.get(team_key) or "").strip().upper()
                    if team:
                        qs = qs.filter(nhl_team_abbr__iexact=team)

                player = qs.first()
                if not player:
                    missing += 1
                    continue

                if player.adp != adp_val:
                    player.adp = adp_val
                    player.save(update_fields=["adp"])
                applied += 1

        self.stdout.write(self.style.SUCCESS(f"ADP applied: {applied}, missing: {missing}, bad rows: {bad}"))

    def handle(self, *args, **kwargs):
        from league.models import Player

        self.stdout.write("Fetching NHL standings...")
        standings = self.safe_json("https://api-web.nhle.com/v1/standings/now")
        teams = standings.get("standings", [])

        imported = 0

        for team in teams:
            team_name = team.get("teamName", {}).get("default", "Unknown")
            team_abbrev = team.get("teamAbbrev", {}).get("default")  # e.g. "WPG"
            if not team_abbrev:
                continue

            self.stdout.write(f"Fetching roster for: {team_name} ({team_abbrev})")
            roster = self.safe_json(f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current")

            players = roster.get("forwards", []) + roster.get("defensemen", []) + roster.get("goalies", [])

            for p in players:
                player_id = p.get("id")
                if not player_id:
                    continue

                info = fetch_landing(int(player_id))
                if not info or "firstName" not in info or "lastName" not in info:
                    continue

                first = info["firstName"].get("default", "") or ""
                last = info["lastName"].get("default", "") or ""
                full_name = info.get("fullName") or f"{first} {last}".strip() or str(player_id)

                pos_code = (info.get("positionCode") or "").strip()
                if pos_code == "UNK":
                    pos_code = ""

                raw_stats = info.get("seasonTotals", {})
                if isinstance(raw_stats, dict):
                    stats = raw_stats
                elif isinstance(raw_stats, list) and raw_stats and isinstance(raw_stats[0], dict):
                    stats = raw_stats[0]
                else:
                    stats = {}

                games = int(stats.get("gamesPlayed", 0) or 0)
                goals = int(stats.get("goals", 0) or 0)
                assists = int(stats.get("assists", 0) or 0)
                points = stats.get("points", None)
                if points is None:
                    points = goals + assists
                points = int(points)

                jersey = info.get("sweaterNumber")
                shoots = info.get("shootsCatches") or ""

                # simple ranking placeholder
                fantasy_score = float(points)

                Player.objects.update_or_create(
                    nhl_id=str(player_id),
                    defaults={
                        "full_name": full_name,
                        "position": pos_code,
                        "shoots": str(shoots),
                        "number": str(jersey) if jersey is not None else "",
                        "nhl_team_abbr": team_abbrev,
                        "games_played": games,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "fantasy_score": fantasy_score,
                        "on_waivers": False,
                        "is_active": True,
                        # ✅ adp left as-is unless you supply --adp-csv
                    },
                )
                imported += 1

        self.stdout.write(self.style.SUCCESS(f"Imported or updated {imported} NHL players successfully."))

        adp_csv = kwargs.get("adp_csv")
        if adp_csv:
            # only works if you added Player.adp field + migrated
            self._apply_adp_csv(Player, adp_csv)
