from django.core.exceptions import ValidationError

def player_fits_slot(player, slot_position):
    """
    Ensures a player can legally fit a lineup slot.
    Example: player.position = "C", slot_position = "LW" → invalid.
    """
    if player.position != slot_position:
        raise ValidationError(
            f"{player.name} cannot play {slot_position}. They are a {player.position}."
        )
    return True

def validate_roster_capacity(team, player):
    from league.models import Roster
    total = Roster.objects.filter(team=team).count()

    if total >= team.league.max_roster_size:
        raise ValidationError("Roster is full.")

def validate_ir_eligibility(player):
    if not player.is_injured:
        raise ValidationError("Player is not eligible for IR.")

def validate_slot_position(slot, player):
    if slot.position not in player.positions.all():
        raise ValidationError(f"{player} cannot play {slot.position}.")
