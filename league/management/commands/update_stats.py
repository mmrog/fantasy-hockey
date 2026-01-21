# league/management/commands/update_player_stats.py
# ✅ NEW COMMAND: updates existing Player rows with current season totals (games/goals/assists/points/fantasy_score)
# Uses the same NHL endpoints as your import command:
#   - standings/now -> list teams
#   - roster/{TEAM}/current -> player ids for that team
#   - player/{id}/landing -> seasonTotals + bio fields
#
# Run:
#   (venv) python manage.py update_player_stats
# Options:
#   (venv) python manage.py update_player_stats --sleep 0.10
#   (venv) python manage.py update_player_stats --teams WPG,TOR,BOS
#   (venv) python manage.py update_player_stats --limit 200
#   (venv) python manage.py update_player_stats --only-existing

from __future__ import annotations

import time
from typing import Any

import requests
from django.core.management.base import BaseCommand


NHL_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def safe_json(url: str, timeout: int = 15, retries: int = 2) -> dict[str, Any]:
    last_err = None
    for _ in range(max(1, retries) + 1):
        try:
            r = requests.get(url, headers=NHL_HEADERS, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise last_err  # type: ignore[misc]


def fetch_landing(player_id: int) -> dict[str, Any] | None:
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    try:
        r = requests.get(url, headers=NHL_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def normalize_season_totals(info: dict[str, Any]) -> dict[str, Any]:
    raw = info.get("seasonTotals", {})
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    return {}


class Command(BaseCommand):
    help = "Update Player stats from the NHL API (games/goals/assists/points/fantasy_score + basic bio fields)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--teams",
            type=str,
            default="",
            help="Comma-separated team abbreviations to update only those teams (e.g. WPG,TOR,BOS). Default: all teams from standings.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.05,
            help="Sleep (seconds) between player landing calls to reduce rate-limit risk. Default: 0.05",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after updating this many players (0 = no limit). Useful for testing.",
        )
        parser.add_argument(
            "--only-existing",
            action="store_true",
            help="Only update players already in your DB (skip creating new ones).",
        )

    def handle(self, *args, **options):
        from league.models import Player  # import after Django loads

        teams_arg: str = (options.get("teams") or "").strip().upper()
        sleep_s: float = float(options.get("sleep") or 0.0)
        limit: int = int(options.get("limit") or 0)
        only_existing: bool = bool(options.get("only_existing"))

        # Build team list
        if teams_arg:
            team_abbrevs = [t.strip() for t in teams_arg.split(",") if t.strip()]
        else:
            self.stdout.write("Fetching NHL standings for team list...")
            standings = safe_json("https://api-web.nhle.com/v1/standings/now")
            rows = standings.get("standings", []) if isinstance(standings, dict) else []
            team_abbrevs = []
            for row in rows:
                abbr = (row.get("teamAbbrev") or {}).get("default")
                if abbr:
                    team_abbrevs.append(str(abbr).upper())
            team_abbrevs = sorted(set(team_abbrevs))

        if not team_abbrevs:
            self.stdout.write(self.style.ERROR("No teams found. Aborting."))
            return

        # Cache existing players by nhl_id if only_existing
        existing_by_nhl_id = {}
        if only_existing:
            existing_by_nhl_id = {p.nhl_id: p for p in Player.objects.all().only("id", "nhl_id")}

        updated = 0
        created = 0
        skipped = 0
        errors = 0

        # We will collect updates and bulk_update every N for speed
        bulk_updates: list[Player] = []
        BULK_EVERY = 250

        self.stdout.write(f"Updating players for teams: {', '.join(team_abbrevs)}")

        for team_abbrev in team_abbrevs:
            try:
                roster = safe_json(f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current")
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.WARNING(f"⚠ Could not fetch roster for {team_abbrev}: {e}"))
                continue

            players = (
                roster.get("forwards", [])
                + roster.get("defensemen", [])
                + roster.get("goalies", [])
            )

            for p in players:
                if limit and (updated + created) >= limit:
                    break

                player_id = p.get("id")
                if not player_id:
                    skipped += 1
                    continue

                nhl_id = str(player_id)

                if only_existing and nhl_id not in existing_by_nhl_id:
                    skipped += 1
                    continue

                info = fetch_landing(int(player_id))
                if not info:
                    errors += 1
                    continue

                first = (info.get("firstName") or {}).get("default", "") or ""
                last = (info.get("lastName") or {}).get("default", "") or ""
                full_name = info.get("fullName") or f"{first} {last}".strip() or nhl_id

                pos_code = (info.get("positionCode") or "").strip()
                if pos_code == "UNK":
                    pos_code = ""

                jersey = info.get("sweaterNumber")
                shoots = info.get("shootsCatches") or ""

                stats = normalize_season_totals(info)
                games = int(stats.get("gamesPlayed", 0) or 0)
                goals = int(stats.get("goals", 0) or 0)
                assists = int(stats.get("assists", 0) or 0)
                points = stats.get("points", None)
                if points is None:
                    points = goals + assists
                points = int(points)

                # placeholder "rank": you’re showing fantasy_score in the UI
                fantasy_score = float(points)

                if only_existing:
                    # Update via bulk_update path
                    obj = Player.objects.get(nhl_id=nhl_id)
                    obj.full_name = full_name
                    obj.position = pos_code
                    obj.number = str(jersey) if jersey is not None else ""
                    obj.shoots = str(shoots)
                    obj.nhl_team_abbr = team_abbrev
                    obj.games_played = games
                    obj.goals = goals
                    obj.assists = assists
                    obj.points = points
                    obj.fantasy_score = fantasy_score
                    obj.is_active = True
                    bulk_updates.append(obj)
                    updated += 1
                else:
                    obj, was_created = Player.objects.update_or_create(
                        nhl_id=nhl_id,
                        defaults={
                            "full_name": full_name,
                            "position": pos_code,
                            "number": str(jersey) if jersey is not None else "",
                            "shoots": str(shoots),
                            "nhl_team_abbr": team_abbrev,
                            "games_played": games,
                            "goals": goals,
                            "assists": assists,
                            "points": points,
                            "fantasy_score": fantasy_score,
                            "is_active": True,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                if sleep_s > 0:
                    time.sleep(sleep_s)

                if only_existing and len(bulk_updates) >= BULK_EVERY:
                    Player.objects.bulk_update(
                        bulk_updates,
                        fields=[
                            "full_name",
                            "position",
                            "number",
                            "shoots",
                            "nhl_team_abbr",
                            "games_played",
                            "goals",
                            "assists",
                            "points",
                            "fantasy_score",
                            "is_active",
                        ],
                    )
                    bulk_updates.clear()

            if limit and (updated + created) >= limit:
                break

        # flush remaining bulk updates
        if only_existing and bulk_updates:
            Player.objects.bulk_update(
                bulk_updates,
                fields=[
                    "full_name",
                    "position",
                    "number",
                    "shoots",
                    "nhl_team_abbr",
                    "games_played",
                    "goals",
                    "assists",
                    "points",
                    "fantasy_score",
                    "is_active",
                ],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated={updated} Created={created} Skipped={skipped} Errors={errors}"
            )
        )
