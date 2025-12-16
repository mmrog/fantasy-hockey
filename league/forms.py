# league/forms.py

from django import forms
from .models import League, LeagueSettings


class LeagueForm(forms.ModelForm):
    """
    Commissioner-only form for core League fields.
    """
    class Meta:
        model = League
        fields = [
            "name",
            "season_year",
            "scoring_mode",
        ]


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
