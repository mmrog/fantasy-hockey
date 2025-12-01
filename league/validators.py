from django.core.exceptions import ValidationError
def player_fits_slot(player, slot):
    """
    slot = Position instance (lineup slot)
    player.position = PlayerPosition instance
    """

    # If commissioner leaves allowed list empty → allow everything
    if slot.allowed_player_positions.count() == 0:
        return

    if not slot.allowed_player_positions.filter(id=player.position.id).exists():
        raise ValidationError(
            f"{player.name} ({player.position.code}) cannot be placed in slot {slot.code}."
        )