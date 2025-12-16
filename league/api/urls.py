# league/api/urls.py

from django.urls import path
from .player_search import player_search
from .players_views import PlayerListAPIView, PlayerDetailAPIView

urlpatterns = [
    # Search autocomplete
    path("players/search/", player_search, name="player_search"),

    # Full list + DRF search filter
    path("players/", PlayerListAPIView.as_view(), name="players_list"),

    # Single player detail
    path("players/<int:pk>/", PlayerDetailAPIView.as_view(), name="player_detail"),
]
