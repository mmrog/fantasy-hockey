# league/admin.py

from django.contrib import admin

from .models import (
    League,
    LeagueRole,
    #Team,
    #Player,
    PlayerPosition,
    Position,
    Roster,
    DailyLineup,
    DailySlot,
    ScoringCategory,
    Draft,
    DraftPick,
    DraftOrder,
)

from .admin_actions import action_generate_draft_order, action_reset_draft_order


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
    ordering = ("league", "user")



# ======================
# TEAM
# ======================
# TEMP DISABLED until Team model is restored
# @admin.register(Team)
# class TeamAdmin(admin.ModelAdmin):
#     list_display = ("name", "league", "manager")
#     search_fields = ("name", "manager__username")
#     list_filter = ("league",)


# ======================
# PLAYER
# ======================
# TEMP DISABLED until Player model is restored
# @admin.register(Player)
# class PlayerAdmin(admin.ModelAdmin):
#     list_display = (
#         "full_name",
#         "position",
#         "number",
#         "shoots",
#         "games_played",
#         "goals",
#         "assists",
#         "points",
#         "fantasy_score",
#         "on_waivers",
#     )
#     search_fields = ("full_name", "nhl_id")
#     list_filter = ("position", "on_waivers")
#     ordering = ("full_name",)

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
    list_display = ("code", "league")
    search_fields = ("code", "league__name")
    list_filter = ("league",)
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
    list_filter = ("team", "date")
    search_fields = ("team__name",)


# ======================
# DAILY SLOT
# ======================
@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    list_display = ("lineup", "player", "slot", "id")
    list_filter = ("slot",)
    search_fields = ("lineup__team__name", "player__full_name")


# ======================
# SCORING CATEGORY
# ======================
@admin.register(ScoringCategory)
class ScoringCategoryAdmin(admin.ModelAdmin):
    list_display = ("league", "stat_key", "name", "weight")
    list_filter = ("league",)
    search_fields = ("league__name", "stat_key")


# ======================
# DRAFT
# ======================
@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "league",
        "draft_type",
        "order_mode",
        "rounds",
        "time_per_pick",
        "scheduled_start",
        "is_active",
        "is_completed",
        "current_pick",
    )
    list_filter = ("draft_type", "order_mode", "is_active", "is_completed")
    search_fields = ("league__name",)
    actions = [action_generate_draft_order, action_reset_draft_order]


@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    list_display = (
        "draft",
        "round_number",
        "pick_number",
        "team",
        "player",
        "made_at",
    )
    list_filter = ("draft", "round_number", "team")
    search_fields = ("player__full_name", "team__name")
    ordering = ("draft", "pick_number")


@admin.register(DraftOrder)
class DraftOrderAdmin(admin.ModelAdmin):
    list_display = ("draft", "team", "position")
    list_filter = ("draft",)
    ordering = ("draft", "position")
