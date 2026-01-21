# league/draft/services.py

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence

from django.db import transaction
from django.utils import timezone

from league.models import Draft, DraftOrder, DraftPick, Player, Roster, Team


@dataclass(frozen=True)
class DraftCreateConfig:
    rounds: int
    time_per_pick: int  # seconds


# ================================================================
# Draft creation: snake or linear + random/alpha/manual order
# ================================================================

@transaction.atomic
def create_or_rebuild_draft(*, draft: Draft, config: DraftCreateConfig) -> Draft:
    """
    Builds DraftOrder + DraftPick grid based on:
      - draft.draft_type: SNAKE / LINEAR
      - draft.order_mode: RANDOM / ALPHA / MANUAL

    MANUAL:
      - expects DraftOrder rows already exist for this draft (positions 1..N)
      - we validate and then build picks from that order
    """
    if config.rounds < 1:
        raise ValueError("rounds must be >= 1")
    if config.time_per_pick < 5:
        raise ValueError("time_per_pick must be >= 5 seconds")

    draft.rounds = config.rounds
    draft.time_per_pick = config.time_per_pick
    draft.is_active = False
    draft.is_completed = False
    draft.current_pick = 1
    draft.started_at = None
    draft.completed_at = None
    draft.current_pick_started_at = None
    draft.save()

    teams = list(Team.objects.filter(league=draft.league).select_related("manager").order_by("id"))
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams in the league to create a draft.")

    # wipe existing grid/order (safe because you're in beta)
    DraftPick.objects.filter(draft=draft).delete()
    if draft.order_mode != "MANUAL":
        DraftOrder.objects.filter(draft=draft).delete()

    base_order = _get_base_order(draft=draft, teams=teams)  # round-1 order

    # build DraftOrder rows (even for snake; order table is still the round-1 base)
    if draft.order_mode != "MANUAL":
        DraftOrder.objects.bulk_create(
            [
                DraftOrder(draft=draft, team=team, position=i)
                for i, team in enumerate(base_order, start=1)
            ],
            batch_size=200,
        )

    # build picks
    picks: List[DraftPick] = []
    pick_number = 1

    for round_number in range(1, draft.rounds + 1):
        round_teams = _teams_for_round(base_order, round_number, draft_type=draft.draft_type)
        for team in round_teams:
            picks.append(
                DraftPick(
                    draft=draft,
                    team=team,
                    player=None,
                    round_number=round_number,
                    pick_number=pick_number,
                    status=DraftPick.STATUS_UPCOMING,
                    started_at=None,
                    made_at=None,
                )
            )
            pick_number += 1

    DraftPick.objects.bulk_create(picks, batch_size=500)
    return draft


def _get_base_order(*, draft: Draft, teams: Sequence[Team]) -> List[Team]:
    """
    Returns the round-1 team order.
    """
    if draft.order_mode == "RANDOM":
        base = list(teams)
        random.shuffle(base)
        return base

    if draft.order_mode == "ALPHA":
        return sorted(list(teams), key=lambda t: (t.name or "").lower())

    if draft.order_mode == "MANUAL":
        rows = list(DraftOrder.objects.filter(draft=draft).select_related("team").order_by("position"))
        if len(rows) != len(teams):
            raise ValueError("MANUAL order_mode requires DraftOrder positions 1..N already created.")
        # validate positions contiguous 1..N
        for idx, row in enumerate(rows, start=1):
            if row.position != idx:
                raise ValueError("DraftOrder positions must be contiguous starting at 1.")
        return [r.team for r in rows]

    raise ValueError(f"Unknown order_mode: {draft.order_mode}")


def _teams_for_round(base_order: Sequence[Team], round_number: int, *, draft_type: str) -> Sequence[Team]:
    """
    SNAKE: odd rounds base, even rounds reversed
    LINEAR: every round base
    """
    if draft_type == "LINEAR":
        return base_order
    # default snake behavior
    if round_number % 2 == 1:
        return base_order
    return list(reversed(base_order))


# ================================================================
# Draft runtime: no pause, always clock + auto-pick
# ================================================================

@transaction.atomic
def start_draft(*, draft: Draft) -> DraftPick:
    if draft.is_completed:
        raise ValueError("Draft is already completed.")

    # ensure picks exist
    if not DraftPick.objects.filter(draft=draft).exists():
        raise ValueError("Draft has no picks. Build the draft grid first.")

    draft.is_active = True
    draft.started_at = draft.started_at or timezone.now()
    draft.current_pick = 1
    draft.current_pick_started_at = timezone.now()
    draft.save(update_fields=["is_active", "started_at", "current_pick", "current_pick_started_at"])

    first = DraftPick.objects.get(draft=draft, pick_number=1)
    _set_on_clock(first)
    return first


def tick_draft(*, draft: Draft) -> Optional[DraftPick]:
    """
    Call this on every draft-room GET + after every pick submission.
    If current pick expired: auto-pick best available (by position need) and advance.
    Returns current ON_CLOCK pick, or None if completed.
    """
    if not draft.is_active or draft.is_completed:
        return None

    current = get_current_pick(draft=draft)
    if current is None:
        # safety repair
        return advance_to_next_pick(draft=draft)

    if is_pick_expired(draft=draft):
        autopick_current(draft=draft)
        return get_current_pick(draft=draft) or (None if draft.is_completed else advance_to_next_pick(draft=draft))

    return current


def get_current_pick(*, draft: Draft) -> Optional[DraftPick]:
    return (
        DraftPick.objects.filter(draft=draft, status=DraftPick.STATUS_ON_CLOCK)
        .select_related("team", "player")
        .first()
    )


@transaction.atomic
def make_pick(*, draft: Draft, user, player_id: int) -> DraftPick:
    """
    Manual pick:
      - must be active
      - user must own the team currently on the clock
      - player must be undrafted in this draft
    """
    if not draft.is_active or draft.is_completed:
        raise ValueError("Draft is not active.")

    current = get_current_pick(draft=draft)
    if current is None:
        raise ValueError("No pick is currently on the clock.")

    if current.team.manager_id != user.id:
        raise PermissionError("Not your pick.")

    if DraftPick.objects.filter(draft=draft, player_id=player_id).exists():
        raise ValueError("Player already drafted.")

    player = Player.objects.get(id=player_id)

    current.player = player
    current.status = DraftPick.STATUS_MADE
    current.made_at = timezone.now()
    current.save(update_fields=["player", "status", "made_at"])

    # roster add (optional but useful for position-need autopick)
    Roster.objects.get_or_create(team=current.team, player=player)

    return advance_to_next_pick(draft=draft) or current


def is_pick_expired(*, draft: Draft) -> bool:
    if not draft.current_pick_started_at:
        return False
    elapsed = timezone.now() - draft.current_pick_started_at
    return elapsed.total_seconds() > draft.time_per_pick


@transaction.atomic
def advance_to_next_pick(*, draft: Draft) -> Optional[DraftPick]:
    next_number = draft.current_pick + 1
    total_picks = draft.rounds * Team.objects.filter(league=draft.league).count()

    if next_number > total_picks:
        draft.is_completed = True
        draft.is_active = False
        draft.completed_at = timezone.now()
        draft.save(update_fields=["is_completed", "is_active", "completed_at"])
        return None

    draft.current_pick = next_number
    draft.current_pick_started_at = timezone.now()
    draft.save(update_fields=["current_pick", "current_pick_started_at"])

    next_pick = DraftPick.objects.get(draft=draft, pick_number=next_number)
    _set_on_clock(next_pick)
    return next_pick


def _set_on_clock(pick: DraftPick) -> None:
    pick.status = DraftPick.STATUS_ON_CLOCK
    pick.started_at = timezone.now()
    pick.save(update_fields=["status", "started_at"])


# ================================================================
# Auto-pick: "highest ranked for position at the time"
# (using fantasy_score as rank for now)
# ================================================================

@transaction.atomic
def autopick_current(*, draft: Draft) -> DraftPick:
    """
    Auto-pick the current ON_CLOCK pick:
      - choose needed position (G until team has 2 goalies, else skater)
      - pick highest fantasy_score available in that bucket
    """
    current = get_current_pick(draft=draft)
    if current is None:
        raise ValueError("No pick on the clock to autopick.")

    preferred = _infer_team_need(team=current.team)

    player = _best_available_player(draft=draft, preferred=preferred)
    if player is None:
        # No players left -> just complete/advance
        current.status = DraftPick.STATUS_AUTO
        current.made_at = timezone.now()
        current.save(update_fields=["status", "made_at"])
        advance_to_next_pick(draft=draft)
        return current

    current.player = player
    current.status = DraftPick.STATUS_AUTO
    current.made_at = timezone.now()
    current.save(update_fields=["player", "status", "made_at"])

    Roster.objects.get_or_create(team=current.team, player=player)

    advance_to_next_pick(draft=draft)
    return current


def _infer_team_need(*, team: Team) -> str:
    """
    Simple rule for now:
      - if team has < 2 goalies on roster, prefer goalies
      - else prefer skaters
    """
    goalie_count = (
        Roster.objects.filter(team=team, player__position__icontains="G").count()
        if hasattr(Player, "position")
        else 0
    )
    return "G" if goalie_count < 2 else "SKATER"


def _best_available_player(*, draft: Draft, preferred: str) -> Optional[Player]:
    drafted_ids = DraftPick.objects.filter(draft=draft).exclude(player_id=None).values_list("player_id", flat=True)
    qs = Player.objects.filter(is_active=True).exclude(id__in=drafted_ids)

    if preferred == "G":
        qs_pref = qs.filter(position__icontains="G")
    elif preferred == "SKATER":
        qs_pref = qs.exclude(position__icontains="G")
    else:
        qs_pref = qs

    # "highest ranked" = highest fantasy_score (you can swap later to ADP/overall_rank)
    player = qs_pref.order_by("-fantasy_score", "full_name").first()
    if player:
        return player

    return qs.order_by("-fantasy_score", "full_name").first()
