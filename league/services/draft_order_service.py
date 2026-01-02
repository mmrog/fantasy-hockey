# league/services/draft_order.py
from __future__ import annotations

import random
from typing import List, Sequence

from django.db import transaction
from django.utils import timezone

from league.models import Draft, DraftOrder, Team


class DraftOrderService:
    """
    Handles:
    - random draft order
    - commissioner-defined order
    - 30-min-before start generation
    NOTE: snake/straight pick sequencing is separate (DraftPick generation service).
    """

    @staticmethod
    def generate_random_order(draft: Draft) -> List[Team]:
        teams = list(Team.objects.filter(league=draft.league).order_by("id"))
        random.shuffle(teams)
        return teams

    @staticmethod
    @transaction.atomic
    def save_draft_order(draft: Draft, ordered_teams: Sequence[Team]) -> None:
        """
        Save assigned positions to DraftOrder table.
        Clears previous entries cleanly.
        """
        DraftOrder.objects.filter(draft=draft).delete()

        DraftOrder.objects.bulk_create(
            [
                DraftOrder(draft=draft, team=team, position=i)
                for i, team in enumerate(ordered_teams, start=1)
            ]
        )

        # Only set this flag if your Draft model actually has it
        if hasattr(draft, "draft_order_generated"):
            draft.draft_order_generated = True
            draft.save(update_fields=["draft_order_generated"])

    @staticmethod
    def should_generate_automatically(draft: Draft) -> bool:
        if getattr(draft, "draft_order_generated", False):
            return False

        starts_at = getattr(draft, "starts_at", None)
        if not starts_at:
            return False

        now = timezone.now()
        trigger_time = starts_at - timezone.timedelta(minutes=30)
        return now >= trigger_time

    @staticmethod
    def auto_generate_if_needed(draft: Draft) -> bool:
        if DraftOrderService.should_generate_automatically(draft):
            teams = DraftOrderService.generate_random_order(draft)
            DraftOrderService.save_draft_order(draft, teams)
            return True
        return False

    @staticmethod
    @transaction.atomic
    def save_manual_order(draft: Draft, team_ids_in_order: Sequence[int]) -> None:
        """
        Commissioner manually sets the exact draft order.

        team_ids_in_order = [3, 1, 5, 2, ...]
        """
        teams = Team.objects.filter(league=draft.league, id__in=team_ids_in_order).only("id")
        team_map = {t.id: t for t in teams}

        # Preserve commissioner-provided order, ignore invalid ids safely
        ordered_teams = [team_map[tid] for tid in team_ids_in_order if tid in team_map]

        DraftOrderService.save_draft_order(draft, ordered_teams)
