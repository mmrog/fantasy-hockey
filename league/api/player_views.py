# league/api/players_views.py

from rest_framework import generics, filters
from league.models import Player
from league.serializers import PlayerSerializer

class PlayerListAPIView(generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["first_name", "last_name", "full_name", "team", "position"]

class PlayerDetailAPIView(generics.RetrieveAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

