from django.contrib import admin
from .models import (
    League,
    LeagueRole,
    Team,
    Player,
    PlayerPosition,
    Position,
    Roster,
    DailyLineup,
    DailySlot,
    ScoringCategory
)

# ======================
# LEAGUE
# ======================
@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "season_year", "commissioner", "scoring_mode")
    search_fields = ("name",)


# ======================
# LEAGUE ROLES
# ======================
@admin.register(LeagueRole)
class LeagueRoleAdmin(admin.ModelAdmin):
    list_display = ("league", "user", "role")
    search_fields = ("league__name", "user__username")
    list_filter = ("role",)


# ======================
# FANTASY TEAM
# ======================
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "league", "manager")
    search_fields = ("name", "manager__username")
    list_filter = ("league",)


# ======================
# PLAYER
# ======================
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "position",
        "number",
        "shoots",
        "games_played",
        "goals",
        "assists",
        "points",
        "fantasy_score",
        "on_waivers",
    )
    search_fields = ("full_name", "nhl_id")
    list_filter = ("position", "on_waivers")
    ordering = ("full_name",)


# ======================
# PLAYER POSITION
# ======================
@admin.register(PlayerPosition)
class PlayerPositionAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code",)


# ======================
# LINEUP SLOT POSITION TYPES
# ======================
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "is_lineup_slot")
    search_fields = ("code",)
    filter_horizontal = ("allowed_player_positions",)


# ======================
# ROSTER
# ======================
@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ("team", "player")
    search_fields = ("team__name", "player__full_name")
    list_filter = ("team",)


# ======================
# DAILY LINEUP
# ======================
@admin.register(DailyLineup)
class DailyLineupAdmin(admin.ModelAdmin):
    list_display = ("team", "date")
    search_fields = ("team__name",)
    list_filter = ("date", "team")


# ======================
# DAILY SLOT
# ======================
@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    list_display = ("lineup", "player", "slot", "id")
    search_fields = ("lineup__team__name", "player__full_name")
    list_filter = ("slot",)


# ======================
# SCORING CATEGORY
# ======================
@admin.register(ScoringCategory)
class ScoringCategoryAdmin(admin.ModelAdmin):
    list_display = ("league", "stat_key", "name", "weight")
    search_fields = ("league__name", "stat_key")
    list_filter = ("league",)
