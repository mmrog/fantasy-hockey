# league/admin_actions.py

from django.contrib import messages
from django.shortcuts import redirect

from .models import DraftOrder


def action_generate_draft_order(modeladmin, request, queryset):
    """
    Admin action: generate draft order for selected drafts.

    Note: This intentionally avoids importing Team directly, because Team may not
    be importable yet (your current issue). We pull teams via the league.team_set
    reverse relation instead.
    """
    for draft in queryset:
        # Delete old order
        DraftOrder.objects.filter(draft=draft).delete()

        # Teams that belong to this league (reverse FK: Team.league -> League)
        # This works as long as Team has a ForeignKey to League named "league".
        teams = draft.league.team_set.all().order_by("id")

        # Create order
        for i, team in enumerate(teams, start=1):
            DraftOrder.objects.create(
                draft=draft,
                team=team,
                position=i,
            )

        # Your Draft model no longer has draft_order_generated
        draft.save()

    messages.success(request, "Draft order generated successfully.")
    return redirect(request.get_full_path())


def action_reset_draft_order(modeladmin, request, queryset):
    """
    Admin action: reset/delete draft order.
    """
    for draft in queryset:
        DraftOrder.objects.filter(draft=draft).delete()

        # Your Draft model no longer has draft_order_generated
        draft.save()

    messages.success(request, "Draft order reset.")
    return redirect(request.get_full_path())
