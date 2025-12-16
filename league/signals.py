from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    League,
    LeagueSettings,
    PlayerPosition,
    Position,
    ScoringCategory,
)

# -----------------------------------------
# DEFAULT SCORING CATEGORIES (league-based)
# -----------------------------------------

DEFAULT_CATEGORIES = [
    # Skaters
    ("goals", "Goals", 1.0),
    ("assists", "Assists", 1.0),
    ("shots", "Shots on Goal", 0.1),
    ("hits", "Hits", 0.25),
    ("blocked", "Blocked Shots", 0.5),
    ("penaltyMinutes", "Penalty Minutes", -0.1),

    # Goalies
    ("wins", "Wins", 4.0),
    ("saves", "Saves", 0.05),
    ("goalsAgainst", "Goals Against", -1.0),
    ("shutouts", "Shutouts", 3.0),
]

# -----------------------------------------
# CREATE DEFAULT POSITIONS + CATEGORY SETUP
# -----------------------------------------

@receiver(post_save, sender=League)
def initialize_league_defaults(sender, instance, created, **kwargs):
    """
    When a league is created, automatically create:
    - LeagueSettings (waiver windows)
    - PlayerPosition entries (C, LW, RW, D, G)
    - Lineup Position slots (C, LW, RW, F, D, G, BN, IR)
    - ScoringCategory entries (Goals, Assists, Hits, Wins, Saves, etc)
    """
    if not created:
        return

    # -----------------------------------------
    # 0. LEAGUE SETTINGS (Waiver windows)
    # -----------------------------------------
    LeagueSettings.objects.get_or_create(
        league=instance,
        defaults={
            "waiver_goalie_hours": 48,
            "waiver_skater_hours": 72,
        }
    )

    # -----------------------------------------
    # 1. PLAYER POSITIONS
    # -----------------------------------------
    base_positions = ["C", "LW", "RW", "D", "G"]
    for code in base_positions:
        PlayerPosition.objects.get_or_create(code=code)

    # -----------------------------------------
    # 2. LINEUP SLOT DEFINITIONS
    # -----------------------------------------
    slot_definitions = {
        "C": ["C"],
        "LW": ["LW"],
        "RW": ["RW"],
        "F": ["C", "LW", "RW"],
        "D": ["D"],
        "G": ["G"],
        "BN": [],   # Bench: any player allowed
        "IR": [],   # Injured Reserve
    }

    for slot_code, allowed_codes in slot_definitions.items():
        slot, _ = Position.objects.get_or_create(
            league=instance,
            code=slot_code,
        )

        # Assign allowed player positions
        for pos_code in allowed_codes:
            pos = PlayerPosition.objects.get(code=pos_code)
            slot.allowed_player_positions.add(pos)

    # -----------------------------------------
    # 3. SCORING CATEGORIES
    # -----------------------------------------
    for stat_key, name, default_weight in DEFAULT_CATEGORIES:
        ScoringCategory.objects.get_or_create(
            league=instance,
            stat_key=stat_key,
            defaults={
                "name": name,
                "weight": default_weight,
            }
        )
