# league/urls.py
# ✅ QUICK FIX FOR TONIGHT: comment out URLs for views you don't currently have in views.py

from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.league_dashboard, name="league_dashboard"),
    path("<int:league_id>/", views.league_dashboard, name="league_dashboard_specific"),

    path("create_league/", views.create_league, name="create_league"),
    path("join_league/", views.join_league, name="join_league"),
    path("create_team/<int:league_id>/", views.create_team, name="create_team_specific"),

    path("team/roster/", views.team_roster, name="team_roster"),
    path("team/lineup/", views.daily_lineup, name="daily_lineup"),

    path("accounts/", include("django.contrib.auth.urls")),

    path("<int:league_id>/commish/", views.commissioner_dashboard, name="commissioner_dashboard"),

    # NEW — draft settings page
    path("<int:league_id>/commish/draft/", views.commish_draft_settings, name="commish_draft_settings"),


    # ---- TEMP DISABLE (these views are not in your current views.py) ----
    # path("<int:league_id>/commish/settings/", views.commish_settings, name="commish_settings"),
    # path("<int:league_id>/commish/league-settings/", views.league_settings, name="league_settings"),
    # path("<int:league_id>/commish/rosters/", views.commish_roster_tools, name="commish_roster_tools"),
    # path("<int:league_id>/commish/rosters/<int:team_id>/edit/", views.commish_edit_team_roster, name="commish_edit_team_roster"),
    # path("<int:league_id>/scoring/", views.scoring_settings, name="scoring_settings"),

    # Matchups (optional)
    path("<int:league_id>/matchups/", views.matchup_day, name="matchup_day"),
    path("<int:league_id>/matchups/<str:day>/", views.matchup_day, name="matchup_day_date"),
]
