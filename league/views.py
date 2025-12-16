from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date

from league.utils.decorators import role_required, commissioner_required

from .models import (
    League,
    LeagueRole,
    Team,
    Player,
    Roster,
    DailyLineup,
    DailySlot,
    ScoringCategory,
    Transaction,
    Trade,   # optional but now supported
    LeagueSettings,
)

from .forms import LeagueForm, WaiverSettingsForm


# -------------------------------------------------------
# HOME = TEAM HUB (if you have a team)
# -------------------------------------------------------
def home(request):
    if not request.user.is_authenticated:
        return redirect("login")

    team = Team.objects.filter(manager=request.user).select_related("league").first()

    if team:
        return render(request, "league/team_home.html", {
            "team": team,
            "league": team.league,
        })
    else:
        return redirect("league_dashboard")


# -------------------------------------------------------
# LEAGUE CREATION (Commissioner)
# -------------------------------------------------------
@login_required
def create_league(request):
    if request.method == "POST":
        name = request.POST.get("name")
        season_year = request.POST.get("season_year")
        scoring_mode = request.POST.get("scoring_mode", "FIXED")

        league = League.objects.create(
            name=name,
            season_year=season_year,
            commissioner=request.user,
            scoring_mode=scoring_mode
        )

        LeagueRole.objects.create(
            league=league,
            user=request.user,
            role="COMMISSIONER"
        )

        return redirect("league_dashboard", league_id=league.id)

    return render(request, "league/create_league.html")


# -------------------------------------------------------
# CREATE TEAM (User)
# -------------------------------------------------------
@login_required
def create_team(request, league_id=None):
    if request.method == "POST":
        name = request.POST["name"]

        if league_id:
            league = get_object_or_404(League, id=league_id)
        else:
            league = League.objects.first()  # temporary fallback

        Team.objects.create(
            name=name,
            league=league,
            manager=request.user
        )

        return redirect("league_dashboard", league_id=league.id)

    leagues = League.objects.all()

    return render(request, "teams/create_team.html", {
        "leagues": leagues
    })


# -------------------------------------------------------
# LEAGUE DASHBOARD (Manager & Commissioner)
# -------------------------------------------------------
@login_required
def league_dashboard(request, league_id=None):
    if league_id:
        league = get_object_or_404(League, id=league_id)
        role = LeagueRole.objects.filter(user=request.user, league=league).first()
    else:
        role = LeagueRole.objects.filter(user=request.user).first()
        league = role.league if role else None

    if not role or not league:
        return render(request, "league/no_league.html")

    team = Team.objects.filter(manager=request.user, league=league).first()

    recent_transactions = (
        Transaction.objects
        .filter(league=league)
        .select_related("team", "player")
        .order_by("-created_at")[:10]
    )

    recent_trades = (
        Trade.objects
        .filter(league=league)
        .select_related("from_team", "to_team")
        .order_by("-created_at")[:5]
    )

    return render(request, "league/dashboard.html", {
        "league": league,
        "team": team,
        "role": role,
        "is_commissioner": role.role in ["COMMISSIONER", "CO_COMMISSIONER"],
        "recent_transactions": recent_transactions,
        "recent_trades": recent_trades,
    })


# -------------------------------------------------------
# COMMISSIONER DASHBOARD + SETTINGS (A1)
# -------------------------------------------------------
@commissioner_required
def commissioner_dashboard(request, league_id):
    league = get_object_or_404(League, id=league_id)

    teams = (
        Team.objects
        .filter(league=league)
        .select_related("manager")
    )

    recent_transactions = (
        Transaction.objects
        .filter(league=league)
        .select_related("team", "player")
        .order_by("-created_at")[:10]
    )

    recent_trades = (
        Trade.objects
        .filter(league=league)
        .select_related("from_team", "to_team")
        .order_by("-created_at")[:5]
    )

    context = {
        "league": league,
        "teams": teams,
        "recent_transactions": recent_transactions,
        "recent_trades": recent_trades,
    }
    return render(request, "league/commissioner_dashboard.html", context)


@commissioner_required
def commish_settings(request, league_id):
    league = get_object_or_404(League, id=league_id)

    if request.method == "POST":
        form = LeagueForm(request.POST, instance=league)
        if form.is_valid():
            form.save()
            messages.success(request, "League settings updated.")
            return redirect("commissioner_dashboard", league_id=league.id)
    else:
        form = LeagueForm(instance=league)

    context = {
        "league": league,
        "form": form,
    }
    return render(request, "league/commish/settings.html", context)


# -------------------------------------------------------
# LEAGUE SETTINGS (Waivers) (Commissioner Only)
# -------------------------------------------------------
@commissioner_required
def league_settings(request, league_id):
    league = get_object_or_404(League, id=league_id)

    settings = LeagueSettings.objects.filter(league=league).first()
    if settings is None:
        settings = LeagueSettings.objects.create(league=league)

    if request.method == "POST":
        form = WaiverSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Waiver settings updated.")
            return redirect("league_dashboard", league_id=league.id)
    else:
        form = WaiverSettingsForm(instance=settings)

    return render(request, "league/commish/waiver_settings.html", {
        "league": league,
        "form": form,
    })


# -------------------------------------------------------
# SCORING SETTINGS (Commissioner Only)
# -------------------------------------------------------
def is_commissioner(user, league):
    return LeagueRole.objects.filter(
        league=league,
        user=user,
        role__in=["COMMISSIONER", "CO_COMMISSIONER"]
    ).exists()


@login_required
def scoring_settings(request, league_id):
    league = get_object_or_404(League, id=league_id)

    if not is_commissioner(request.user, league):
        return redirect("home")

    categories = ScoringCategory.objects.filter(league=league)

    if request.method == "POST":
        for cat in categories:
            field = f"weight_{cat.id}"
            new_weight = request.POST.get(field)

            if new_weight:
                try:
                    cat.weight = float(new_weight)
                    cat.save()
                except ValueError:
                    pass

        return redirect("scoring_settings", league_id=league.id)

    return render(request, "league/scoring_settings.html", {
        "league": league,
        "categories": categories,
    })


# -------------------------------------------------------
# COMMISSIONER ROSTER TOOLS
# -------------------------------------------------------
@commissioner_required
def commish_roster_tools(request, league_id):
    league = get_object_or_404(League, id=league_id)

    teams = (
        Team.objects
        .filter(league=league)
        .select_related("manager")
    )

    context = {
        "league": league,
        "teams": teams,
    }
    return render(request, "league/commish/roster_tools.html", context)


@commissioner_required
def commish_edit_team_roster(request, league_id, team_id):
    league = get_object_or_404(League, id=league_id)
    team = get_object_or_404(Team, id=team_id, league=league)

    roster = (
        Roster.objects
        .filter(team=team)
        .select_related("player")
    )

    context = {
        "league": league,
        "team": team,
        "roster": roster,
    }
    return render(request, "league/commish/edit_team_roster.html", context)


# -------------------------------------------------------
# TEAM ROSTER
# -------------------------------------------------------
@login_required
def team_roster(request, league_id=None):
    team = Team.objects.filter(manager=request.user).first()

    if not team:
        return render(request, "league/no_team.html")

    roster = Roster.objects.filter(team=team).select_related("player")

    return render(request, "league/team_roster.html", {
        "team": team,
        "roster": roster,
    })


# -------------------------------------------------------
# DAILY LINEUP
# -------------------------------------------------------
@login_required
def daily_lineup(request, league_id=None):
    team = Team.objects.filter(manager=request.user).first()

    if not team:
        return render(request, "league/no_team.html")

    lineup, created = DailyLineup.objects.get_or_create(
        team=team,
        date=date.today(),
    )

    slots = DailySlot.objects.filter(lineup=lineup).select_related("player", "slot")

    return render(request, "league/daily_lineup.html", {
        "team": team,
        "lineup": lineup,
        "slots": slots,
    })
