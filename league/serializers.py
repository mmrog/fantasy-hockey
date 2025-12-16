from rest_framework import serializers
from league.models import Player


class PlayerSerializer(serializers.ModelSerializer):
    position = serializers.CharField(source="position.code")
    position_name = serializers.CharField(source="position.description", read_only=True)

    class Meta:
        model = Player
        fields = [
            "id",
            "nhl_id",
            "full_name",
            "first_name",
            "last_name",
            "position",
            "position_name",
            "number",
            "shoots",
            "headshot",
            "games_played",
            "goals",
            "assists",
            "points",
            "shots",
            "hits",
            "fantasy_score",
        ]
