from django.core.management.base import BaseCommand
from league.models import Player, League, Roster
from league.utils.scoring import calculate_player_score

class Command(BaseCommand):
    help = "Recalculate fantasy scores for all players in all leagues"

    def handle(self, *args, **kwargs):
        leagues = League.objects.all()
        updated = 0

        for league in leagues:
            # all players who belong to teams in this league
            rostered_players = Player.objects.filter(
                roster__team__league=league
            ).distinct()

            for player in rostered_players:
                player.fantasy_score = calculate_player_score(player, league)
                player.save(update_fields=["fantasy_score"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Recalculated fantasy scores for {updated} players."
        ))
