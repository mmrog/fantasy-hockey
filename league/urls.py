from django.urls import path, include
from . import views

urlpatterns = [
    # ------------------------
    # League Dashboard
    # ------------------------
    path("", views.league_dashboard, name="league_dashboard"),
    path("<int:league_id>/", views.league_dashboard, name="league_dashboard_specific"),

    # ------------------------
    # Team Pages
    # ------------------------
    path("team/roster/", views.team_roster, name="team_roster"),
    path("team/lineup/", views.daily_lineup, name="daily_lineup"),

    # ------------------------
    # League / Team Creation
    # ------------------------
    path("create_league/", views.create_league, name="create_league"),
    path("create_team/", views.create_team, name="create_team"),
    path("create_team/<int:league_id>/", views.create_team, name="create_team_specific"),

    # ------------------------
    # Authentication
    # ------------------------
    path("accounts/", include("django.contrib.auth.urls")),

    # ------------------------
    # Commissioner Dashboard
    # ------------------------
    path("<int:league_id>/commish/", views.commissioner_dashboard, name="commissioner_dashboard"),

    # ------------------------
    # Commissioner Settings (League fields)
    # ------------------------
    path("<int:league_id>/commish/settings/", views.commish_settings, name="commish_settings"),

    # ------------------------
    # Commissioner League Settings (Waivers)
    # matches your dashboard button: {% url 'league_settings' league.id %}
    # ------------------------
    path("<int:league_id>/commish/league-settings/", views.league_settings, name="league_settings"),

    # ------------------------
    # Roster Override Tool
    # ------------------------
    path("<int:league_id>/commish/rosters/", views.commish_roster_tools, name="commish_roster_tools"),
    path(
        "<int:league_id>/commish/rosters/<int:team_id>/edit/",
        views.commish_edit_team_roster,
        name="commish_edit_team_roster",
    ),

    # ------------------------
    # Scoring Settings
    # ------------------------
    path("<int:league_id>/scoring/", views.scoring_settings, name="scoring_settings"),
]
