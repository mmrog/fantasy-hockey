from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date

from league.utils.decorators import role_required

from .models import (
    League,
    LeagueRole,
    Team,
    Player,
    Roster,
    DailyLineup,
    DailySlot
)

def home(request):
    return render(request, "home.html")


# -----------------------------
# Create League (Commissioner)
# -----------------------------
@login_required
def create_league(request):
    if request.method == "POST":
        name = request.POST.get("name")
        season_year = request.POST.get("season_year")
        scoring_mode = request.POST.get("scoring_mode")

        league = League.objects.create(
            name=name,
            season_year=season_year,
            commissioner=request.user,
            scoring_mode=scoring_mode
        )

        # Assign commissioner role
        LeagueRole.objects.create(
            league=league,
            user=request.user,
            role="COMMISSIONER"
        )

        return redirect("league_dashboard")

    return render(request, "league/create_league.html")


# -----------------------------
# Create Team
# -----------------------------
@login_required
def create_team(request):
    if request.method == "POST":
        name = request.POST["name"]

        league = League.objects.first()  # temporary placeholder

        Team.objects.create(
            name=name,
            league=league,
            manager=request.user
        )

        return redirect("league_dashboard")

    return render(request, "teams/create_team.html")


# -----------------------------
# League Dashboard
# -----------------------------
@login_required
def league_dashboard(request):
    roles = LeagueRole.objects.filter(user=request.user)

    if not roles.exists():
        return render(request, "league/no_league.html")

    role = roles.first()
    league = role.league

    team = Team.objects.filter(manager=request.user, league=league).first()

    return render(request, "league/dashboard.html", {
        "league": league,
        "team": team,
        "role": role,
        "is_commissioner": role.role in ["COMMISSIONER", "CO_COMMISSIONER"],
    })


# -----------------------------
# Team Roster
# -----------------------------
@login_required
def team_roster(request):
    team = Team.objects.filter(manager=request.user).first()
    roster = Roster.objects.filter(team=team)

    return render(request, "league/team_roster.html", {
        "team": team,
        "roster": roster
    })


# -----------------------------
# Daily Lineup
# -----------------------------
@login_required
def daily_lineup(request):
    team = get_object_or_404(Team, manager=request.user)

    lineup, created = DailyLineup.objects.get_or_create(
        team=team,
        date=date.today()
    )

    slots = DailySlot.objects.filter(lineup=lineup).select_related("player")

    return render(request, "league/daily_lineup.html", {
        "team": team,
        "lineup": lineup,
        "slots": slots,
    })


# -----------------------------
# League Settings (COMMISSIONER ONLY)
# -----------------------------
@role_required("COMMISSIONER")
def league_settings(request, league_id):
    league = get_object_or_404(League, id=league_id)

    if request.method == "POST":
        league.name = request.POST.get("name", league.name)
        league.season_year = request.POST.get("season_year", league.season_year)
        league.save()

    return render(request, "league/settings.html", {
        "league": league
    })
