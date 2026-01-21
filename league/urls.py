# league/urls.py
# ✅ UPDATED (matches the updated views.py you are using)

from django.urls import path, include
from . import views

urlpatterns = [
    # League dashboard
    path("", views.league_dashboard, name="league_dashboard"),
    path("<int:league_id>/", views.league_dashboard, name="league_dashboard_specific"),

    # Create / Join
    path("create_league/", views.create_league, name="create_league"),
    path("join_league/", views.join_league, name="join_league"),
    path("create_team/<int:league_id>/", views.create_team, name="create_team_specific"),

    # ✅ Team Home (team_id, not league_id)
    path("team/<int:team_id>/", views.team_home, name="team_home"),

    # ✅ Team pages (league_id-based routes)
    path("<int:league_id>/team/roster/", views.team_roster, name="team_roster"),
    path("<int:league_id>/team/lineup/", views.daily_lineup, name="daily_lineup"),

    # Auth
    path("accounts/", include("django.contrib.auth.urls")),

    # Commissioner
    path("<int:league_id>/commish/", views.commissioner_dashboard, name="commissioner_dashboard"),
    path("<int:league_id>/commish/draft/", views.commish_draft_settings, name="commish_draft_settings"),
    path("<int:league_id>/commish/draft/build/", views.commish_draft_build, name="commish_draft_build"),
    path("<int:league_id>/commish/draft/start/", views.commish_draft_start, name="commish_draft_start"),
    path("<int:league_id>/commish/draft/manual-order/", views.commish_manual_draft_order, name="commish_manual_draft_order"),

    # Draft Room
    path("<int:league_id>/draft/", views.draft_room, name="draft_room"),

    # ✅ Players tab for managers
    path("<int:league_id>/players/", views.team_players, name="team_players"),

    # Matchups
    path("<int:league_id>/matchups/", views.matchup_day, name="matchup_day"),
    path("<int:league_id>/matchups/<str:day>/", views.matchup_day, name="matchup_day_date"),
]
