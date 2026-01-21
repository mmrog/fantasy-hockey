# league/admin.py
from django.contrib import admin

from league.draft.services import DraftCreateConfig, create_or_rebuild_draft, start_draft

from .models import (
    DailyLineup,
    DailySlot,
    Draft,
    DraftOrder,
    DraftPick,
    League,
    LeagueRole,
    Player,
    PlayerPosition,
    Position,
    Roster,
    ScoringCategory,
    Team,
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
    list_filter = ("role",)
    search_fields = ("league__name", "user__username")
    ordering = ("league", "user")


# ======================
# TEAM
# ======================
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "league", "manager")
    list_filter = ("league",)
    search_fields = ("name", "manager__username", "league__name")
    ordering = ("league", "name")


# ======================
# PLAYER
# ======================
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "nhl_team_abbr",
        "position",
        "nhl_id",
        "adp",
        "is_active",
        "on_waivers",
    )
    search_fields = ("full_name", "nhl_team_abbr", "nhl_id")
    list_filter = ("nhl_team_abbr", "position", "is_active", "on_waivers")
    ordering = ("full_name",)

    fields = (
        "full_name",
        "nhl_id",
        "nhl_team_abbr",
        "position",
        "number",
        "shoots",
        "adp",
        "is_active",
        "on_waivers",
        "games_played",
        "goals",
        "assists",
        "points",
        "fantasy_score",
    )

# ======================
# PLAYER POSITION
# ======================
@admin.register(PlayerPosition)
class PlayerPositionAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code", "description")


# ======================
# LINEUP POSITIONS
# ======================
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("code", "league", "slots")
    list_filter = ("league",)
    search_fields = ("code", "league__name")
    filter_horizontal = ("allowed_player_positions",)


# ======================
# ROSTER
# ======================
@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ("team", "player")
    list_filter = ("team__league", "team")
    search_fields = ("team__name", "player__full_name")


# ======================
# DAILY LINEUP
# ======================
@admin.register(DailyLineup)
class DailyLineupAdmin(admin.ModelAdmin):
    list_display = ("team", "date")
    list_filter = ("team__league", "team", "date")
    search_fields = ("team__name",)


@admin.register(DailySlot)
class DailySlotAdmin(admin.ModelAdmin):
    list_display = ("lineup", "slot", "player", "id")
    list_filter = ("slot",)
    search_fields = ("lineup__team__name", "player__full_name")


# ======================
# SCORING CATEGORY
# ======================
@admin.register(ScoringCategory)
class ScoringCategoryAdmin(admin.ModelAdmin):
    list_display = ("league", "stat_key", "name", "weight", "lower_is_better", "is_goalie")
    list_filter = ("league", "is_goalie", "lower_is_better")
    search_fields = ("league__name", "stat_key", "name")


# ======================
# DRAFT ACTIONS
# ======================
@admin.action(description="Build draft grid (uses draft_type + order_mode)")
def action_build_draft_grid(modeladmin, request, queryset):
    for draft in queryset:
        create_or_rebuild_draft(
            draft=draft,
            config=DraftCreateConfig(rounds=draft.rounds, time_per_pick=draft.time_per_pick),
        )


@admin.action(description="Start draft (clock begins immediately)")
def action_start_draft(modeladmin, request, queryset):
    for draft in queryset:
        start_draft(draft=draft)


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
    actions = (action_build_draft_grid, action_start_draft)


@admin.register(DraftPick)
class DraftPickAdmin(admin.ModelAdmin):
    list_display = (
        "draft",
        "round_number",
        "pick_number",
        "team",
        "player",
        "status",
        "started_at",
        "made_at",
    )
    list_filter = ("draft", "round_number", "team", "status")
    search_fields = ("player__full_name", "team__name")
    ordering = ("draft", "round_number", "pick_number")


@admin.register(DraftOrder)
class DraftOrderAdmin(admin.ModelAdmin):
    list_display = ("draft", "team", "position")
    list_filter = ("draft",)
    ordering = ("draft", "position")
