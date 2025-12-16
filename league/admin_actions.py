from django.contrib import messages
from django.shortcuts import redirect
from .models import Draft, DraftOrder, Team

def action_generate_draft_order(modeladmin, request, queryset):
    """
    Admin action: generate draft order for selected drafts.
    """
    for draft in queryset:
        # Delete old order
        DraftOrder.objects.filter(draft=draft).delete()

        # Teams that belong to this league
        teams = Team.objects.filter(league=draft.league).order_by("id")

        # Create order
        position = 1
        for team in teams:
            DraftOrder.objects.create(
                draft=draft,
                team=team,
                position=position,
            )
            position += 1

        draft.draft_order_generated = True
        draft.save()

    messages.success(request, "Draft order generated successfully.")
    return redirect(request.get_full_path())


def action_reset_draft_order(modeladmin, request, queryset):
    """
    Admin action: reset/delete draft order.
    """
    for draft in queryset:
        DraftOrder.objects.filter(draft=draft).delete()
        draft.draft_order_generated = False
        draft.save()

    messages.success(request, "Draft order reset.")
    return redirect(request.get_full_path())
