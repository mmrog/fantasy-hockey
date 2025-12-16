import random
from django.utils import timezone
from league.models import Draft, DraftOrder, Team


class DraftOrderService:
    """
    Handles:
    - random draft order
    - commissioner-defined order
    - snake/straight logic handled later
    - automatic 30-min-before start generation
    """

    @staticmethod
    def generate_random_order(draft: Draft):
        """
        Randomly shuffle all teams in the league.
        """
        teams = list(Team.objects.filter(league=draft.league))
        random.shuffle(teams)
        return teams

    @staticmethod
    def save_draft_order(draft: Draft, ordered_teams):
        """
        Save assigned positions to DraftOrder table.
        Clears previous entries cleanly.
        """
        DraftOrder.objects.filter(draft=draft).delete()

        for i, team in enumerate(ordered_teams, start=1):
            DraftOrder.objects.create(
                draft=draft,
                team=team,
                position=i
            )

        draft.draft_order_generated = True
        draft.save()

    @staticmethod
    def should_generate_automatically(draft: Draft):
        """
        Check if 30 minutes before draft start time has been reached.
        """
        if draft.draft_order_generated:
            return False

        if not draft.starts_at:
            return False

        now = timezone.now()
        trigger_time = draft.starts_at - timezone.timedelta(minutes=30)

        return now >= trigger_time

    @staticmethod
    def auto_generate_if_needed(draft: Draft):
        """
        If it's time, generate random draft order.
        Returns True if generated.
        """
        if DraftOrderService.should_generate_automatically(draft):
            teams = DraftOrderService.generate_random_order(draft)
            DraftOrderService.save_draft_order(draft, teams)
            return True

        return False

    @staticmethod
    def save_manual_order(draft: Draft, team_ids_in_order):
        """
        Commissioner manually sets the exact draft order.

        team_ids_in_order = [3, 1, 5, 2, ...]
        """
        ordered_teams = list(
            Team.objects.filter(id__in=team_ids_in_order, league=draft.league)
        )

        ordered_teams.sort(key=lambda t: team_ids_in_order.index(t.id))

        DraftOrderService.save_draft_order(draft, ordered_teams)
  