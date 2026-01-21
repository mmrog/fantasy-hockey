# league/views.py
# ✅ CLEAN FULL FILE
# - ONE home
# - ONE team_home(team_id) -> renders league/team_home.html
# - team_roster(league_id), daily_lineup(league_id) match your urls.py
# - team_players(league_id) exists (fixes "no attribute team_players")
# - draft_room(league_id) uses DraftPick.round_number/pick_number (NO overall_pick)
# - Rank sorting uses ADP (Player.adp) with blanks last

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from league.draft.services import (
    DraftCreateConfig,
    create_or_rebuild_draft,
    make_pick,
    start_draft,
    tick_draft,
)
from league.utils.decorators import commissioner_required

from .forms import DraftSettingsForm, JoinLeagueForm, LeagueCreateForm, TeamCreateForm
from .models import (
    DailyLineup,
    DailySlot,
    Draft,
    DraftOrder,
    DraftPick,
    League,
    LeagueRole,
    LeagueSettings,
    Player,
    PlayerPosition,
    Position,
    Roster,
    ScoringCategory,
    Team,
)
from .models_matchups import Matchup


# -------------------------------------------------------
# HOME
# -------------------------------------------------------
@login_required
def home(request):
    team = request.user.team_set.select_related("league").first()
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

            LeagueSettings.objects.get_or_create(
                league=league,
                defaults={"goalie_waiver_hours": 48, "skater_waiver_hours": 72},
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
                Position.objects.get_or_create(league=league, code=code, defaults={"slots": slots})

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
                obj, _ = PlayerPosition.objects.get_or_create(code=code, defaults={"description": desc})
                pp[code] = obj

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
def create_team(request, league_id: int):
    league = get_object_or_404(League, id=league_id)

    LeagueRole.objects.get_or_create(
        league=league,
        user=request.user,
        defaults={"role": "MANAGER"},
    )

    existing = Team.objects.filter(league=league, manager=request.user).first()
    if existing:
        messages.info(request, "You already have a team in this league.")
        return redirect("team_home", team_id=existing.id)

    if request.method == "POST":
        form = TeamCreateForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.league = league
            team.manager = request.user
            team.save()

            messages.success(request, f"Team '{team.name}' created.")
            return redirect("team_home", team_id=team.id)
    else:
        form = TeamCreateForm()

    return render(request, "league/create_team.html", {"form": form, "league": league})


# -------------------------------------------------------
# TEAM HOME (single team page)
# -------------------------------------------------------
@login_required
def team_home(request, team_id: int):
    team = get_object_or_404(Team.objects.select_related("league", "manager"), pk=team_id)

    roster_qs = Roster.objects.filter(team=team).select_related("player")
    roster_count = roster_qs.count()
    goalie_count = roster_qs.filter(player__position__iexact="G").count()
    skater_count = roster_count - goalie_count

    pos_counts = {}
    for code in ["C", "LW", "RW", "D", "G"]:
        cnt = roster_qs.filter(player__position__iexact=code).count()
        if cnt:
            pos_counts[code] = cnt

    return render(
        request,
        "league/team_home.html",
        {
            "team": team,
            "league": team.league,  # ✅ template convenience
            "roster_count": roster_count,
            "goalie_count": goalie_count,
            "skater_count": skater_count,
            "pos_counts": pos_counts,
        },
    )


# -------------------------------------------------------
# TEAM ROSTER (matches urls.py: <int:league_id>/team/roster/)
# -------------------------------------------------------
@login_required
def team_roster(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    team = league.team_set.filter(manager=request.user).first()
    if not team:
        return render(request, "league/no_team.html")

    roster = Roster.objects.filter(team=team).select_related("player")
    return render(request, "league/team_roster.html", {"league": league, "team": team, "roster": roster})


# -------------------------------------------------------
# DAILY LINEUP (matches urls.py: <int:league_id>/team/lineup/)
# -------------------------------------------------------
@login_required
def daily_lineup(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    team = league.team_set.filter(manager=request.user).first()
    if not team:
        return render(request, "league/no_team.html")

    lineup, _ = DailyLineup.objects.get_or_create(team=team, date=timezone.now().date())
    slots = DailySlot.objects.filter(lineup=lineup).select_related("player", "slot")
    return render(
        request,
        "league/daily_lineup.html",
        {"league": league, "team": team, "lineup": lineup, "slots": slots},
    )


# -------------------------------------------------------
# PLAYERS TAB (fixes urls.py: views.team_players)
# -------------------------------------------------------
@login_required
def team_players(request, league_id: int):
    league = get_object_or_404(League, id=league_id)

    role = LeagueRole.objects.filter(league=league, user=request.user).first()
    if not role:
        return HttpResponseForbidden("You are not a member of this league.")

    team = league.team_set.filter(manager=request.user).first()

    tab = (request.GET.get("tab") or "free_agents").strip().lower()  # free_agents | waivers
    q = (request.GET.get("q") or "").strip()
    pos = (request.GET.get("pos") or "ALL").upper().strip()
    sort = (request.GET.get("sort") or "name").strip().lower()
    page = request.GET.get("page") or 1

    rostered_ids = Roster.objects.filter(team__league=league).values_list("player_id", flat=True)

    players_qs = Player.objects.filter(is_active=True)
    if tab == "waivers":
        players_qs = players_qs.filter(on_waivers=True)
    else:
        tab = "free_agents"
        players_qs = players_qs.exclude(id__in=rostered_ids)

    if q:
        players_qs = players_qs.filter(full_name__icontains=q)

    if pos != "ALL":
        players_qs = players_qs.filter(position__iexact=pos)

    pos_codes = list(
        Position.objects.filter(league=league).order_by("code").values_list("code", flat=True).distinct()
    )
    pos_options = ["ALL"] + pos_codes

    if sort == "rank":
        # ADP-ish manager list: use fantasy_score first (you can switch to adp later if you want)
        players_qs = players_qs.order_by("-fantasy_score", "-points", "full_name")
    elif sort == "team":
        players_qs = players_qs.order_by("nhl_team_abbr", "full_name")
    else:
        sort = "name"
        players_qs = players_qs.order_by("full_name")

    paginator = Paginator(players_qs, 50)
    page_obj = paginator.get_page(page)

    return render(
        request,
        "league/team/players.html",
        {
            "league": league,
            "team": team,
            "tab": tab,
            "q": q,
            "pos": pos,
            "sort": sort,
            "pos_options": pos_options,
            "players": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


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
    is_commissioner = league.commissioner_id == request.user.id or role.role in ("COMMISSIONER", "CO_COMMISSIONER")

    return render(
        request,
        "league/dashboard.html",
        {"league": league, "team": team, "role": role, "is_commissioner": is_commissioner},
    )


# -------------------------------------------------------
# COMMISH: DASHBOARD + DRAFT SETTINGS + BUILD/START
# -------------------------------------------------------
@login_required
@commissioner_required
def commissioner_dashboard(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    members = LeagueRole.objects.filter(league=league).select_related("user")
    teams = league.team_set.select_related("manager")
    draft = Draft.objects.filter(league=league).first()

    return render(
        request,
        "league/commish/commissioner_dashboard.html",
        {"league": league, "members": members, "teams": teams, "draft": draft, "draft_ready": teams.count() >= 2},
    )


@login_required
@commissioner_required
def commish_draft_settings(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    draft, _ = Draft.objects.get_or_create(league=league)

    if request.method == "POST":
        form = DraftSettingsForm(request.POST, instance=draft)
        if form.is_valid():
            draft = form.save()
            messages.success(request, "Draft settings saved.")
            if draft.order_mode == "MANUAL":
                return redirect("commish_manual_draft_order", league_id=league.id)
            return redirect("commissioner_dashboard", league_id=league.id)
    else:
        form = DraftSettingsForm(instance=draft)

    return render(request, "league/commish/draft_settings.html", {"league": league, "draft": draft, "form": form})


@login_required
@commissioner_required
def commish_manual_draft_order(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    draft, _ = Draft.objects.get_or_create(league=league)

    if draft.is_active:
        messages.error(request, "Draft is active. Draft order is locked.")
        return redirect("commissioner_dashboard", league_id=league.id)

    teams = list(league.team_set.all().order_by("id"))
    if len(teams) < 2:
        messages.error(request, "Need at least 2 teams to set a draft order.")
        return redirect("commissioner_dashboard", league_id=league.id)

    existing = list(draft.order.select_related("team").all().order_by("position"))
    if not existing:
        existing = [DraftOrder(draft=draft, team=t, position=i + 1) for i, t in enumerate(teams)]

    if request.method == "POST":
        seen = set()
        new_team_ids = []

        for pos in range(1, len(teams) + 1):
            tid = request.POST.get(f"pos_{pos}")
            if not tid:
                messages.error(request, f"Missing team for position {pos}.")
                return redirect("commish_manual_draft_order", league_id=league.id)
            if tid in seen:
                messages.error(request, "Each team can only appear once in the order.")
                return redirect("commish_manual_draft_order", league_id=league.id)

            seen.add(tid)
            new_team_ids.append(int(tid))

        team_by_id = {t.id: t for t in teams}
        try:
            new_teams = [team_by_id[tid] for tid in new_team_ids]
        except KeyError:
            messages.error(request, "Invalid team selection.")
            return redirect("commish_manual_draft_order", league_id=league.id)

        with transaction.atomic():
            DraftOrder.objects.filter(draft=draft).delete()
            DraftOrder.objects.bulk_create(
                [DraftOrder(draft=draft, team=t, position=i + 1) for i, t in enumerate(new_teams)]
            )

            if draft.order_mode != "MANUAL":
                draft.order_mode = "MANUAL"
                draft.save(update_fields=["order_mode"])

        messages.success(request, "Manual draft order saved. Now click Build Draft Grid.")
        return redirect("commish_draft_settings", league_id=league.id)

    return render(
        request,
        "league/commish/manual_draft_order.html",
        {"league": league, "draft": draft, "teams": teams, "existing": existing},
    )


@login_required
@commissioner_required
def commish_draft_build(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    draft, _ = Draft.objects.get_or_create(league=league)

    if league.team_set.count() < 2:
        messages.error(request, "Need at least 2 teams to build a draft.")
        return redirect("commissioner_dashboard", league_id=league.id)

    if draft.order_mode == "MANUAL" and not draft.order.exists():
        messages.info(request, "Manual order selected. Set the draft order first.")
        return redirect("commish_manual_draft_order", league_id=league.id)

    try:
        config = DraftCreateConfig(rounds=draft.rounds, time_per_pick=draft.time_per_pick)
        create_or_rebuild_draft(draft=draft, config=config)
        messages.success(request, "Draft grid built (order + picks).")
    except Exception as e:
        messages.error(request, f"Draft build failed: {e}")

    return redirect("draft_room", league_id=league.id)


@login_required
@commissioner_required
def commish_draft_start(request, league_id: int):
    league = get_object_or_404(League, id=league_id)
    draft, _ = Draft.objects.get_or_create(league=league)

    try:
        start_draft(draft=draft)
        messages.success(request, "Draft started. Pick #1 is on the clock.")
    except Exception as e:
        messages.error(request, f"Could not start draft: {e}")

    return redirect("draft_room", league_id=league.id)


# -------------------------------------------------------
# DRAFT ROOM (ADP rank; DraftPick uses round_number/pick_number)
# -------------------------------------------------------
@login_required
def draft_room(request, league_id: int):
    league = get_object_or_404(League, id=league_id)

    role = LeagueRole.objects.filter(user=request.user, league=league).first()
    if not role:
        return HttpResponseForbidden("You are not a member of this league.")

    is_commissioner = league.commissioner_id == request.user.id or role.role in ("COMMISSIONER", "CO_COMMISSIONER")

    draft = Draft.objects.filter(league=league).first()
    if not draft:
        draft = Draft.objects.create(league=league)

    try:
        tick_draft(draft)
    except Exception:
        pass

    # POST: make pick
    if request.method == "POST":
        player_id = request.POST.get("player_id")
        if player_id:
            try:
                make_pick(draft=draft, user=request.user, player_id=int(player_id))
                messages.success(request, "Pick submitted.")
                return redirect("draft_room", league_id=league.id)
            except Exception as e:
                messages.error(request, f"Pick failed: {e}")

    drafted_ids = DraftPick.objects.filter(draft=draft, player__isnull=False).values_list("player_id", flat=True)

    draft_order = [o.team for o in DraftOrder.objects.filter(draft=draft).select_related("team").order_by("position")]

    picks = (
        DraftPick.objects.filter(draft=draft, player__isnull=False)
        .select_related("player", "team")
        .order_by("round_number", "pick_number")
    )

    current_pick_obj = (
        DraftPick.objects.filter(draft=draft, player__isnull=True)
        .select_related("team")
        .order_by("round_number", "pick_number")
        .first()
    )
    on_the_clock_team = current_pick_obj.team if current_pick_obj else None

    queue = DraftPick.objects.filter(draft=draft, player__isnull=True).order_by("round_number", "pick_number")[:10]

    # ----------------------------
    # filters + sorting + paging
    # ----------------------------
    selected_pos = (request.GET.get("pos") or "ALL").upper().strip()
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "rank").strip().lower()
    direction = (request.GET.get("dir") or "asc").strip().lower()
    page_number = request.GET.get("page") or 1

    pos_codes = list(
        Position.objects.filter(league=league).order_by("code").values_list("code", flat=True).distinct()
    )
    pos_options = ["ALL"] + pos_codes
    if selected_pos not in pos_options:
        selected_pos = "ALL"

    available_qs = Player.objects.filter(is_active=True).exclude(id__in=drafted_ids)

    if q:
        available_qs = available_qs.filter(full_name__icontains=q)

    if selected_pos != "ALL":
        pos_obj = (
            Position.objects.filter(league=league, code=selected_pos)
            .prefetch_related("allowed_player_positions")
            .first()
        )
        if pos_obj:
            allowed_codes = list(pos_obj.allowed_player_positions.values_list("code", flat=True))
            if allowed_codes:
                available_qs = available_qs.filter(position__in=allowed_codes)
            else:
                available_qs = available_qs.filter(position__iexact=selected_pos)
        else:
            available_qs = available_qs.filter(position__iexact=selected_pos)

    if direction not in ("asc", "desc"):
        direction = "asc"

    prefix = "-" if direction == "desc" else ""

    if sort == "rank":
        # ✅ ADP (lower is better). Blanks last.
        available_qs = available_qs.order_by(
            F("adp").asc(nulls_last=True) if direction == "asc" else F("adp").desc(nulls_last=True),
            "full_name",
        )
    elif sort == "team":
        available_qs = available_qs.order_by(f"{prefix}nhl_team_abbr", "full_name")
    else:
        sort = "name"
        available_qs = available_qs.order_by(f"{prefix}full_name")

    params = request.GET.copy()
    params.pop("page", None)
    qs = params.urlencode()

    paginator = Paginator(available_qs, 300)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "league/draft/draft_room.html",
        {
            "league": league,
            "draft": draft,
            "is_commissioner": is_commissioner,
            "draft_order": draft_order,
            "picks": picks,
            "queue": queue,
            "on_the_clock_team": on_the_clock_team,
            "current_pick": (
                f"R{current_pick_obj.round_number} P{current_pick_obj.pick_number}"
                if current_pick_obj
                else None
            ),
            "selected_pos": selected_pos,
            "pos_options": pos_options,
            "page_obj": page_obj,
            "available_players": page_obj.object_list,
            "qs": qs,
        },
    )


# -------------------------------------------------------
# MATCHUPS
# -------------------------------------------------------
@login_required
def matchup_day(request, league_id, day=None):
    league = get_object_or_404(League, id=league_id)
    score_day = date.fromisoformat(day) if day else timezone.localdate()

    matchups = (
        Matchup.objects.filter(league=league, date=score_day)
        .select_related("home_team", "away_team")
        .prefetch_related("category_results", "category_results__category")
    )

    return render(request, "league/matchup_day.html", {"league": league, "day": score_day, "matchups": matchups})
