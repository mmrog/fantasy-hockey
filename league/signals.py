from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import League, PlayerPosition, Position


@receiver(post_save, sender=League)
def create_default_positions(sender, instance, created, **kwargs):
    """
    Creates the basic PlayerPositions and Position slots
    when a new league is created.
    """
    if not created:
        return

    # Default NHL player positions
    base_positions = ["C", "LW", "RW", "D", "G"]
    for code in base_positions:
        PlayerPosition.objects.get_or_create(code=code)

    # Default lineup slot structure
    slot_definitions = {
        "C": ["C"],
        "LW": ["LW"],
        "RW": ["RW"],
        "F": ["C", "LW", "RW"],
        "D": ["D"],
        "G": ["G"],
        "BN": [],   # any player allowed
        "IR": [],   # any player allowed, injury validated elsewhere
    }

    for slot_code, allowed_list in slot_definitions.items():
        slot, created = Position.objects.get_or_create(code=slot_code)
        # assign allowed positions
        for pos_code in allowed_list:
            pos = PlayerPosition.objects.get(code=pos_code)
            slot.allowed_player_positions.add(pos)
