import random
from django.utils import timezone
from league.models import DraftOrder, Draft

def maybe_randomize_draft_order(draft: Draft):
    """
    Runs 30 minutes before draft time if order_type is RANDOM.
    Does nothing if already randomized.
    """
    if draft.order_type != "RANDOM":
        return False

    if draft.randomized:
        return False

    if not draft.draft_datetime:
        return False

    now = timezone.now()
    if now < draft.draft_datetime - timezone.timedelta(minutes=30):
        return False  # Too early

    # Get all league teams
    teams = list(draft.league.team_set.all())
    random.shuffle(teams)

    # Assign positions
    DraftOrder.objects.filter(draft=draft).delete()
    for i, team in enumerate(teams, start=1):
        DraftOrder.objects.create(
            draft=draft,
            team=team,
            position=i
        )

    draft.randomized = True
    draft.save()

    return True
