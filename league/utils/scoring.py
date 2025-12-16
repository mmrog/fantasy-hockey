from league.models import ScoringCategory

def get_scoring_weights(league):
    """
    Returns a dict like:
    {
        "goals": 1.0,
        "assists": 1.0,
        "shots": 0.1,
        ...
    }
    """
    categories = ScoringCategory.objects.filter(league=league)
    return {cat.stat_key: cat.weight for cat in categories}

def calculate_player_score(player, league):
    """
    Calculate a fantasy score for a single player,
    using the league's scoring weights.
    """

    weights = get_scoring_weights(league)

    # Extract player stats
    stats = {
        "goals": player.goals,
        "assists": player.assists,
        "shots": player.shots,
        "hits": player.hits,
        "plus_minus": player.plus_minus,
        "games_played": player.games_played,

        # goalie stats (if applicable)
        "wins": getattr(player, "wins", 0),
        "saves": getattr(player, "saves", 0),
    }

    total = 0.0

    # Multiply each stat by its league weight
    for stat_key, value in stats.items():
        weight = weights.get(stat_key)
        if weight is not None and value is not None:
            total += float(value) * float(weight)

    return round(total, 2)
