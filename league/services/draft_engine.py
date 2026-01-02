# league/services/draft_engine.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from league.models import Draft, DraftOrder, DraftPick, Player, Roster


@dataclass(frozen=True)
class DraftClock:
    """Pure computed state for the current pick."""
    pick_number: int
    round_number: int
    pick_in_round: int  # 1..team_count
    team_id: int
    team_name: str


def _team_count(draft: Draft) -> int:
    return DraftOrder.objects.filter(draft=draft).count()


def _require_order_exists(draft: Draft) -> None:
    if not DraftOrder.objects.filter(draft=draft).exists():
        raise ValidationError("Draft order does not exist. Run generate_draft_order first.")


def compute_round_pick(draft: Draft, pick_number: Optional[int] = None) -> Tuple[int, int]:
    """
    Returns (round_number, pick_in_round) for a given pick number.
    pick_in_round is 1..team_count
    """
    _require_order_exists(draft)

    n = _team_count(draft)
    if n < 2:
        raise ValidationError("Draft must have at least 2 teams in the order.")

    p = pick_number or draft.current_pick
    if p < 1:
        raise ValidationError("Pick number must be >= 1.")

    # Example: n=10
    # picks 1..10 => round 1, 1..10
    # picks 11..20 => round 2, 1..10
    round_number = ((p - 1) // n) + 1
    pick_in_round = ((p - 1) % n) + 1
    return round_number, pick_in_round


def _team_for_linear(draft: Draft, round_number: int, pick_in_round: int) -> DraftOrder:
    return DraftOrder.objects.get(draft=draft, position=pick_in_round)


def _team_for_snake(draft: Draft, round_number: int, pick_in_round: int, n: int) -> DraftOrder:
    # Odd rounds: 1..n
    # Even rounds: n..1
    if round_number % 2 == 1:
        pos = pick_in_round
    else:
        pos = (n - pick_in_round) + 1
    return DraftOrder.objects.get(draft=draft, position=pos)


def get_current_clock(draft: Draft) -> DraftClock:
    """
    Compute who is on the clock for draft.current_pick.
    """
    _require_order_exists(draft)
    n = _team_count(draft)

    round_number, pick_in_round = compute_round_pick(draft, draft.current_pick)

    if round_number > draft.rounds:
        # Past the end; draft should be completed.
        # We still return a safe-ish state by clamping to last possible pick.
        round_number = draft.rounds
        pick_in_round = n

    if draft.draft_type == "LINEAR":
        order_row = _team_for_linear(draft, round_number, pick_in_round)
    else:
        order_row = _team_for_snake(draft, round_number, pick_in_round, n)

    return DraftClock(
        pick_number=draft.current_pick,
        round_number=round_number,
        pick_in_round=pick_in_round,
        team_id=order_row.team_id,
        team_name=order_row.team.name,
    )


def is_draft_complete(draft: Draft) -> bool:
    _require_order_exists(draft)
    n = _team_count(draft)
    total_picks = draft.rounds * n
    return draft.current_pick > total_picks


def _validate_pick_allowed(draft: Draft) -> None:
    if not draft.is_active:
        raise ValidationError("Draft is not active.")
    if draft.is_completed:
        raise ValidationError("Draft is already completed.")
    if is_draft_complete(draft):
        raise ValidationError("Draft has no remaining picks.")


def _validate_player_available(draft: Draft, player: Player) -> None:
    # Player cannot be picked twice in the same draft
    if DraftPick.objects.filter(draft=draft, player=player).exists():
        raise ValidationError("Player has already been drafted.")


def _add_player_to_team_roster(team_id: int, player: Player) -> None:
    # Basic roster insert. If you have extra rules later (max size, slot fit),
    # this is where they go.
    Roster.objects.create(team_id=team_id, player=player)


@transaction.atomic
def start_draft(draft: Draft) -> Draft:
    """
    Commissioner action: mark draft active + set started_at if not set.
    """
    _require_order_exists(draft)

    if draft.is_completed:
        raise ValidationError("Cannot start a completed draft.")

    if draft.started_at is None:
        draft.started_at = timezone.now()

    draft.is_active = True
    draft.save(update_fields=["is_active", "started_at"])
    return draft


@transaction.atomic
def pause_draft(draft: Draft) -> Draft:
    """
    Commissioner action: pause the draft.
    """
    if draft.is_completed:
        raise ValidationError("Draft is completed.")
    draft.is_active = False
    draft.save(update_fields=["is_active"])
    return draft


@transaction.atomic
def make_pick(draft: Draft, player_id: int) -> DraftPick:
    """
    Create a pick for the current team on the clock, add player to roster,
    and advance current_pick. No undo.
    """
    _require_order_exists(draft)
    _validate_pick_allowed(draft)

    clock = get_current_clock(draft)

    player = Player.objects.select_for_update().get(id=player_id)
    _validate_player_available(draft, player)

    # Create pick
    pick = DraftPick.objects.create(
        draft=draft,
        team_id=clock.team_id,
        player=player,
        round_number=clock.round_number,
        pick_number=clock.pick_number,
        made_at=timezone.now(),
    )

    # Add to roster (simple)
    _add_player_to_team_roster(clock.team_id, player)

    # Advance pick
    draft.current_pick += 1

    # Complete draft if needed
    if is_draft_complete(draft):
        draft.is_active = False
        draft.is_completed = True
        draft.completed_at = timezone.now()
        draft.save(update_fields=["current_pick", "is_active", "is_completed", "completed_at"])
    else:
        draft.save(update_fields=["current_pick"])

    return pick


def current_team(draft: Draft) -> Tuple[int, str]:
    """
    Convenience helper: (team_id, team_name) for who is on the clock now.
    """
    clock = get_current_clock(draft)
    return clock.team_id, clock.team_name
