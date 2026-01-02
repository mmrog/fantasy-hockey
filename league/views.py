# league/views.py

from datetime import date, date as date_type

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from league.utils.decorators import commissioner_required

from .forms import (
    LeagueCreateForm,
    TeamCreateForm,
    WaiverSettingsForm,
    JoinLeagueForm,
    DraftSettingsForm,
)
from .models import (
    League,
    LeagueRole,
    # Team,   # TEMP: Team model currently missing from league/models.py
    # Player, # TEMP: Player model currently missing from league/models.py
    PlayerPosition,
    Position,
    Roster,
    DailyLineup,
    DailySlot,
    ScoringCategory,
    Transaction,
    Trade,
    LeagueSettings,
    Draft,
)
from .models_matchups import Matchup


# -------------------------------------------------------
# HOME
# -------------------------------------------------------
@login_required
def home(request):
    # Use reverse relation (League -> Team) without importing Team directly
    # This assumes your Team model has: league = models.ForeignKey(League, ...)
    # and: manager = models.ForeignKey(User, ...)
    team = (
        request.user.team_set.select_related("league")
        .first()
    )
    if team:
        return redirect("league_dashboard_specific", league_id=team.league.id)
    return redirect("league_dashboard")


# -------------------------------------------------------
# JOIN LEAGUE (Manager)
# -------------------------------------------------------
@login_required
def join_league(request):
    if request.method == "POST":
        form = JoinLeagueForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["invite_code"]
            league = get_object_or_404(League, invite_code=code)

            LeagueRole.objects.get_or_create(
                league=league,
                user=request.user,
                defaults={"role": "MANAGER"},
            )

            # Check if this user already has a team in this league without importing Team
            if league.team_set.filter(manager=request.user).exists():
                messages.info(request, "You're already in this league and have a team.")
                return redirect("league_dashboard_specific", league_id=league.id)

            messages.success(request, f"Joined '{league.name}'. Now create your team.")
            return redirect("create_team_specific", league_id=league.id)
    else:
        form = JoinLeagueForm()

    return render(request, "league/join_league.html", {"form": form})


# -------------------------------------------------------
# CREATE LEAGUE (Commissioner)
# -------------------------------------------------------
@login_required
@transaction.atomic
def create_league(request):
    if request.method == "POST":
        form = LeagueCreateForm(request.POST)
        if form.is_valid():
            league = form.save(commit=False)
            league.commissioner = request.user
            league.save()

            LeagueRole.objects.get_or_create(
                league=league,
                user=request.user,
                defaults={"role": "COMMISSIONER"},
            )

            # Default LeagueSettings
            LeagueSettings.objects.get_or_create(
                league=league,
                defaults={
                    "goalie_waiver_hours": 48,
                    "skater_waiver_hours": 72,
                },
            )

            # Default lineup positions + slot counts
            DEFAULT_POSITIONS = {
                "C": 2,
                "LW": 2,
                "RW": 2,
                "F": 1,
                "D": 4,
                "G": 2,
                "BN": 4,
                "IR": 2,
            }
            for code, slots in DEFAULT_POSITIONS.items():
                Position.objects.get_or_create(
                    league=league,
                    code=code,
                    defaults={"slots": slots},
                )

            # Default player positions (global)
            core_pp = [
                ("C", "Center"),
                ("LW", "Left Wing"),
                ("RW", "Right Wing"),
                ("D", "Defense"),
                ("G", "Goalie"),
            ]
            pp = {}
            for code, desc in core_pp:
                obj, _ = PlayerPosition.objects.get_or_create(
                    code=code,
                    defaults={"description": desc},
                )
                pp[code] = obj

            # Allowed player positions per lineup slot
            allowed_map = {
                "C": ["C"],
                "LW": ["LW"],
                "RW": ["RW"],
                "F": ["C", "LW", "RW"],
                "D": ["D"],
                "G": ["G"],
                "BN": ["C", "LW", "RW", "D", "G"],
                "IR": ["C", "LW", "RW", "D", "G"],
            }
            for pos in Position.objects.filter(league=league):
                codes = allowed_map.get(pos.code)
                if codes:
                    pos.allowed_player_positions.set([pp[c] for c in codes])

            # Default scoring categories
            defaults = [
                ("G", "Goals", 1.0, False, False),
                ("A", "Assists", 1.0, False, False),
                ("PLUS_MINUS", "Plus/Minus", 1.0, False, False),
                ("PIM", "Penalty Minutes", 1.0, False, False),
                ("PPP", "Power Play Points", 1.0, False, False),
                ("SHG", "Short-Handed Goals", 1.0, False, False),
                ("GWG", "Game-Winning Goals", 1.0, False, False),
                ("SOG", "Shots", 1.0, False, False),
                ("HIT", "Hits", 1.0, False, False),
                ("BLK", "Blocks", 1.0, False, False),
                ("W", "Wins", 1.0, False, True),
                ("GA", "Goals Against", 1.0, True, True),
                ("SV", "Saves", 1.0, False, True),
                ("SO", "Shutouts", 1.0, False, True),
            ]
            for stat_key, name, weight, lower_is_better, is_goalie in defaults:
                ScoringCategory.objects.get_or_create(
                    league=league,
                    stat_key=stat_key,
                    defaults={
                        "name": name,
                        "weight": weight,
                        "lower_is_better": lower_is_better,
                        "is_goalie": is_goalie,
                    },
                )

            messages.success(request, f"League '{league.name}' created.")
            return redirect("create_team_specific", league_id=league.id)

        messages.error(request, "Please fix the errors below.")
        return render(request, "league/create_league.html", {"form": form})

    form = LeagueCreateForm()
    return render(request, "league/create_league.html", {"form": form})


# -------------------------------------------------------
# CREATE TEAM
# -------------------------------------------------------
@login_required
@transaction.atomic
def create_team(request, league_id):
    league = get_object_or_404(League, id=league_id)

    if not LeagueRole.objects.filter(league=league, user=request.user).exists():
        messages.error(request, "Join the league before creating a team.")
        return redirect("join_league")

    if request.method == "POST":
        form = TeamCreateForm(request.POST)
        if form.is_valid():
            if league.team_set.filter(manager=request.user).exists():
                return redirect("league_dashboard_specific", league_id=league.id)

            team = form.save(commit=False)
            team.league = league
            team.manager = request.user
            team.save()

            LeagueRole.objects.get_or_create(
                league=league,
                user=request.user,
                defaults={"role": "MANAGER"},
            )

            return redirect("league_dashboard_specific", league_id=league.id)
    else:
        form = TeamCreateForm()

    return render(request, "league/create_team.html", {"form": form, "league": league})


# -------------------------------------------------------
# LEAGUE DASHBOARD
# -------------------------------------------------------
@login_required
def league_dashboard(request, league_id=None):
    role = LeagueRole.objects.filter(user=request.user).first()
    league = role.league if role else None

    if league_id:
        league = get_object_or_404(League, id=league_id)
        role = LeagueRole.objects.filter(user=request.user, league=league).first()

    if not league or not role:
        return render(request, "league/no_league.html")

    team = league.team_set.filter(manager=request.user).first()

    return render(
        request,
        "league/dashboard.html",
        {"league": league, "team": team, "role": role},
    )


# -------------------------------------------------------
# COMMISSIONER DASHBOARD
# -------------------------------------------------------
@login_required
@commissioner_required
def commissioner_dashboard(request, league_id):
    league = get_object_or_404(League, id=league_id)

    members = LeagueRole.objects.filter(league=league).select_related("user")
    teams = league.team_set.select_related("manager")

    return render(
        request,
        "league/commish/commissioner_dashboard.html",
        {
            "league": league,
            "members": members,
            "teams": teams,
            "draft_ready": teams.count() >= 2,
        },
    )

# -------------------------------------------------------
# COMMISH: DRAFT SETTINGS
# -------------------------------------------------------
@login_required
@commissioner_required
def commish_draft_settings(request, league_id):
    league = get_object_or_404(League, id=league_id)

    draft, _ = Draft.objects.get_or_create(league=league)

    if request.method == "POST":
        form = DraftSettingsForm(request.POST, instance=draft)
        if form.is_valid():
            form.save()
            messages.success(request, "Draft settings saved.")
            return redirect("commissioner_dashboard", league_id=league.id)
    else:
        form = DraftSettingsForm(instance=draft)

    return render(
        request,
        "league/commish/draft_settings.html",
        {"league": league, "draft": draft, "form": form},
    )
# -------------------------------------------------------
# DAILY LINEUP
# -------------------------------------------------------
@login_required
def daily_lineup(request):
    team = request.user.team_set.first()
    if not team:
        return render(request, "league/no_team.html")

    lineup, _ = DailyLineup.objects.get_or_create(team=team, date=date.today())
    slots = DailySlot.objects.filter(lineup=lineup).select_related("player", "slot")

    return render(
        request,
        "league/daily_lineup.html",
        {"team": team, "lineup": lineup, "slots": slots},
    )


@login_required
def team_roster(request, league_id=None):
    team = request.user.team_set.first()
    if not team:
        return render(request, "league/no_team.html")

    roster = Roster.objects.filter(team=team).select_related("player")

    return render(
        request,
        "league/team_roster.html",
        {"team": team, "roster": roster},
    )


# -------------------------------------------------------
# MATCHUPS
# -------------------------------------------------------
@login_required
def matchup_day(request, league_id, day=None):
    league = get_object_or_404(League, id=league_id)
    score_day = date_type.fromisoformat(day) if day else timezone.localdate()

    matchups = (
        Matchup.objects.filter(league=league, date=score_day)
        .select_related("home_team", "away_team")
        .prefetch_related("category_results", "category_results__category")
    )

    return render(
        request,
        "league/matchup_day.html",
        {"league": league, "day": score_day, "matchups": matchups},
    )
