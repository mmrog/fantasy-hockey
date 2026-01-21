# league/forms.py

from django import forms

from .models import (
    League,
    LeagueSettings,
    Draft,
    Team,
)


# ================================================================
# LEAGUE
# ================================================================

class LeagueCreateForm(forms.ModelForm):
    class Meta:
        model = League
        fields = ["name", "season_year", "scoring_mode"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "League name", "class": "form-control"}
            ),
            "season_year": forms.NumberInput(
                attrs={"min": 2000, "max": 2100, "class": "form-control"}
            ),
            "scoring_mode": forms.Select(attrs={"class": "form-select"}),
        }


# ================================================================
# TEAM
# ================================================================

class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Team name", "class": "form-control"}
            ),
        }


# ================================================================
# LEAGUE SETTINGS
# ================================================================

class WaiverSettingsForm(forms.ModelForm):
    """
    Commissioner-only form for waiver timing rules.
    """
    class Meta:
        model = LeagueSettings
        fields = [
            "goalie_waiver_hours",
            "skater_waiver_hours",
        ]
        widgets = {
            "goalie_waiver_hours": forms.NumberInput(attrs={"class": "form-control"}),
            "skater_waiver_hours": forms.NumberInput(attrs={"class": "form-control"}),
        }


# ================================================================
# JOIN LEAGUE
# ================================================================

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
            "scheduled_start": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "draft_type": forms.Select(attrs={"class": "form-select"}),
            "order_mode": forms.Select(attrs={"class": "form-select"}),
            "rounds": forms.NumberInput(attrs={"class": "form-control"}),
            "time_per_pick": forms.NumberInput(attrs={"class": "form-control"}),
        }
