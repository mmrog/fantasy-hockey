# league/forms.py
from django import forms
from django.apps import apps

from .models import League, LeagueSettings, Draft


class LeagueCreateForm(forms.ModelForm):
    class Meta:
        model = League
        fields = ["name", "season_year", "scoring_mode"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "League name"}),
            "season_year": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }


class TeamCreateForm(forms.ModelForm):
    """
    Team creation form.
    We resolve the Team model lazily to avoid import errors while Team
    is temporarily missing from league/models.py.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Team = apps.get_model("league", "Team")
        self._meta.model = Team

    class Meta:
        model = None  # set dynamically in __init__
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Team name"}),
        }


class WaiverSettingsForm(forms.ModelForm):
    """
    Commissioner-only form for waiver timing rules.
    Matches the existing LeagueSettings model fields.
    """
    class Meta:
        model = LeagueSettings
        fields = [
            "goalie_waiver_hours",
            "skater_waiver_hours",
        ]


class JoinLeagueForm(forms.Form):
    invite_code = forms.CharField(
        max_length=12,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Invite code (e.g. A1B2C3D4E5F6)",
                "class": "form-control",
            }
        ),
    )

    def clean_invite_code(self):
        return (self.cleaned_data["invite_code"] or "").strip().upper()


# ================================================================
# DRAFT
# ================================================================

class DraftSettingsForm(forms.ModelForm):
    """
    Commissioner-only draft configuration.
    Minimal fields needed to run the draft room.
    """
    class Meta:
        model = Draft
        fields = [
            "scheduled_start",
            "draft_type",
            "order_mode",
            "rounds",
            "time_per_pick",
        ]
        widgets = {
            "scheduled_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
