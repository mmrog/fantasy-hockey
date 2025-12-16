# league/api/player_search.py

from rest_framework.decorators import api_view
from rest_framework.response import Response
from league.models import Player
from league.serializers import PlayerSerializer


@api_view(["GET"])
def player_search(request):
    """
    Search for players by name fragment.
    Example: /api/players/search?q=mcd
    """
    query = request.GET.get("q", "").strip()

    if not query:
        return Response({"results": []})

    players = Player.objects.filter(full_name__icontains=query).order_by("full_name")[:25]

    serializer = PlayerSerializer(players, many=True)
    return Response({"results": serializer.data})
