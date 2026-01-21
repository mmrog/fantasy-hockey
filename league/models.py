# league/models.py
from __future__ import annotations

import secrets

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from .validators import player_fits_slot


# ================================================================
# LEAGUE + ROLES
# ================================================================

class League(models.Model):
    SCORING_MODES = [
        ("FIXED", "Fixed"),
        ("CUSTOM", "Custom (Commissioner Editable)"),
    ]

    name = models.CharField(max_length=100)
    season_year = models.IntegerField(default=2025)

    commissioner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="commissioned_leagues",
    )

    scoring_mode = models.CharField(
        max_length=10,
        choices=SCORING_MODES,
        default="FIXED",
    )

    invite_code = models.CharField(max_length=12, unique=True, blank=True, db_index=True)

    skater_waiver_hours = models.PositiveIntegerField(default=72)
    goalie_waiver_hours = models.PositiveIntegerField(default=48)

    max_roster_size = models.PositiveIntegerField(default=20)
    bench_slots = models.PositiveIntegerField(default=3)
    ir_slots = models.PositiveIntegerField(default=2)

    lock_hour = models.PositiveSmallIntegerField(default=17)
    lock_minute = models.PositiveSmallIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = secrets.token_hex(6).upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.season_year})"


class LeagueRole(models.Model):
    ROLE_CHOICES = [
        ("COMMISSIONER", "Commissioner"),
        ("CO_COMMISSIONER", "Co-Commissioner"),
        ("MANAGER", "Manager"),
    ]

    league = models.ForeignKey("League", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "user"], name="uniq_league_role"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.role}"


# ================================================================
# TEAM + PLAYER
# ================================================================

class Team(models.Model):
    league = models.ForeignKey("League", on_delete=models.CASCADE)
    manager = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "name"], name="uniq_team_name_per_league"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.league.name})"


class Player(models.Model):
    nhl_id = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=120, db_index=True)

    # C/LW/RW/D/G
    position = models.CharField(max_length=10, blank=True)

    number = models.CharField(max_length=10, blank=True)
    shoots = models.CharField(max_length=10, blank=True)

    # NHL team abbr (ex: "WPG")
    nhl_team_abbr = models.CharField(max_length=3, blank=True, default="", db_index=True)

    # ADP (Average Draft Position). Lower = better.
    adp = models.FloatField(null=True, blank=True, db_index=True)

    games_played = models.PositiveIntegerField(default=0)
    goals = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=0)

    # placeholder “rank/score” you can replace later
    fantasy_score = models.FloatField(default=0.0)

    on_waivers = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


# ================================================================
# PLAYER POSITIONS (Independent of League)
# ================================================================

class PlayerPosition(models.Model):
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return self.code


# ================================================================
# LINEUP POSITIONS (Depend on League)
# ================================================================

class Position(models.Model):
    league = models.ForeignKey("League", on_delete=models.CASCADE)
    code = models.CharField(max_length=10)
    slots = models.PositiveSmallIntegerField(default=0)

    allowed_player_positions = models.ManyToManyField(
        "PlayerPosition",
        blank=True,
        related_name="allowed_in_positions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "code"], name="uniq_position_code_per_league"),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.league.name})"


# ================================================================
# DRAFT MODELS
# ================================================================

class Draft(models.Model):
    DRAFT_TYPES = [
        ("SNAKE", "Snake"),
        ("LINEAR", "Linear"),
    ]

    ORDER_MODES = [
        ("RANDOM", "Random"),
        ("MANUAL", "Manual"),
        ("ALPHA", "Alphabetical"),
    ]

    league = models.OneToOneField("League", on_delete=models.CASCADE, related_name="draft")

    scheduled_start = models.DateTimeField(null=True, blank=True)

    draft_type = models.CharField(max_length=10, choices=DRAFT_TYPES, default="SNAKE")
    order_mode = models.CharField(max_length=10, choices=ORDER_MODES, default="RANDOM")

    rounds = models.PositiveIntegerField(default=16)
    time_per_pick = models.PositiveIntegerField(default=120, help_text="Seconds per pick")

    is_active = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)

    current_pick = models.PositiveIntegerField(default=1)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # server-side clock enforcement
    current_pick_started_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Draft – {self.league.name}"


class DraftOrder(models.Model):
    draft = models.ForeignKey("Draft", on_delete=models.CASCADE, related_name="order")
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["draft", "position"], name="uniq_draft_order_position"),
            models.UniqueConstraint(fields=["draft", "team"], name="uniq_draft_order_team"),
        ]
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.draft} – {self.position}: {self.team.name}"


class DraftPick(models.Model):
    STATUS_UPCOMING = "UPCOMING"
    STATUS_ON_CLOCK = "ON_CLOCK"
    STATUS_MADE = "MADE"
    STATUS_AUTO = "AUTO"

    STATUSES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ON_CLOCK, "On the clock"),
        (STATUS_MADE, "Made"),
        (STATUS_AUTO, "Auto-picked"),
    ]

    draft = models.ForeignKey("Draft", on_delete=models.CASCADE, related_name="picks")

    # dynasty-ready: original owner + current owner
    original_team = models.ForeignKey(
        "Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_picks_original",
    )
    team = models.ForeignKey(
        "Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_picks_owned",
    )

    player = models.ForeignKey("Player", on_delete=models.SET_NULL, null=True, blank=True)

    round_number = models.PositiveIntegerField()
    pick_number = models.PositiveIntegerField()

    status = models.CharField(max_length=10, choices=STATUSES, default=STATUS_UPCOMING)
    started_at = models.DateTimeField(null=True, blank=True)
    made_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # ✅ pick_number repeats each round, so include round_number
            models.UniqueConstraint(
                fields=["draft", "round_number", "pick_number"],
                name="uniq_draft_round_pick_number",
            ),
        ]
        ordering = ["round_number", "pick_number"]

    def __str__(self) -> str:
        who = self.player.full_name if self.player else "—"
        owner = self.team.name if self.team else "Unassigned"
        return f"R{self.round_number} P{self.pick_number} – {owner} – {who}"

    def clean(self):
        # once draft is active, prevent changing ownership
        if not self.pk:
            return

        old = type(self).objects.filter(pk=self.pk).only("team_id", "original_team_id").first()
        if not old:
            return

        if self.draft and self.draft.is_active:
            if old.team_id != self.team_id:
                raise ValidationError("Draft is active: pick ownership is locked.")
            if old.original_team_id != self.original_team_id:
                raise ValidationError("Draft is active: original owner is locked.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# ================================================================
# ROSTERS
# ================================================================

class Roster(models.Model):
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    player = models.ForeignKey("Player", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "player"], name="uniq_roster_team_player"),
        ]

    def __str__(self) -> str:
        return f"{self.team} — {self.player}"


# ================================================================
# DAILY LINEUPS
# ================================================================

class DailyLineup(models.Model):
    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "date"], name="uniq_daily_lineup_team_date"),
        ]

    def __str__(self) -> str:
        return f"{self.team.name} — {self.date}"


class DailySlot(models.Model):
    lineup = models.ForeignKey("DailyLineup", on_delete=models.CASCADE)
    player = models.ForeignKey("Player", on_delete=models.SET_NULL, null=True, blank=True)
    slot = models.ForeignKey("Position", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lineup", "slot"], name="uniq_daily_slot_lineup_slot"),
        ]

    def clean(self):
        if self.player:
            player_fits_slot(self.player, self.slot)

        if DailySlot.objects.filter(lineup=self.lineup, slot=self.slot).exclude(id=self.id).exists():
            raise ValidationError(f"Slot {self.slot.code} already assigned.")

        if self.player and not Roster.objects.filter(team=self.lineup.team, player=self.player).exists():
            raise ValidationError(f"{self.player.full_name} is not on this team's roster.")

    def __str__(self) -> str:
        return f"{self.lineup.date} — {self.slot.code}"


# ================================================================
# SCORING CATEGORIES
# ================================================================

class ScoringCategory(models.Model):
    league = models.ForeignKey("League", on_delete=models.CASCADE)

    stat_key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)

    lower_is_better = models.BooleanField(default=False)
    is_goalie = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "stat_key"], name="uniq_scoring_key_per_league"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} - {self.league.name}"


# ================================================================
# LEAGUE SETTINGS
# ================================================================

class LeagueSettings(models.Model):
    league = models.OneToOneField("League", on_delete=models.CASCADE)

    goalie_waiver_hours = models.IntegerField(default=48)
    skater_waiver_hours = models.IntegerField(default=72)

    weekly_move_limit = models.IntegerField(default=4)
    goalie_min_games = models.IntegerField(default=3)

    slots_c = models.IntegerField(default=2)
    slots_lw = models.IntegerField(default=2)
    slots_rw = models.IntegerField(default=2)
    slots_f = models.IntegerField(default=1)
    slots_d = models.IntegerField(default=4)
    slots_g = models.IntegerField(default=2)
    slots_bn = models.IntegerField(default=3)
    slots_ir = models.IntegerField(default=2)

    def __str__(self) -> str:
        return f"Settings for {self.league.name}"


# ================================================================
# ADVANCED STATS
# ================================================================

class PlayerAdvancedStats(models.Model):
    player = models.OneToOneField("Player", on_delete=models.CASCADE)
    season = models.CharField(max_length=9, default="2024-25")

    corsi_for = models.FloatField(default=0)
    corsi_against = models.FloatField(default=0)
    corsi_pct = models.FloatField(default=0)

    fenwick_for = models.FloatField(default=0)
    fenwick_against = models.FloatField(default=0)
    fenwick_pct = models.FloatField(default=0)

    xg = models.FloatField(default=0)
    ixg = models.FloatField(default=0)
    xga = models.FloatField(default=0)
    xgf_pct = models.FloatField(default=0)

    hdcf = models.FloatField(default=0)
    hdca = models.FloatField(default=0)
    hdcf_pct = models.FloatField(default=0)

    points_per_60 = models.FloatField(default=0)
    goals_per_60 = models.FloatField(default=0)
    assists_per_60 = models.FloatField(default=0)

    updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.player.full_name} Advanced Stats ({self.season})"


# ================================================================
# TRANSACTIONS
# ================================================================

class Transaction(models.Model):
    league = models.ForeignKey("League", on_delete=models.CASCADE)
    team = models.ForeignKey("Team", on_delete=models.SET_NULL, null=True, blank=True)
    player = models.ForeignKey("Player", on_delete=models.SET_NULL, null=True, blank=True)

    action = models.CharField(max_length=50)
    note = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} — {self.player} ({self.created_at})"


# ================================================================
# TRADES
# ================================================================

class Trade(models.Model):
    league = models.ForeignKey("League", on_delete=models.CASCADE)
    from_team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="trades_sent")
    to_team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="trades_received")

    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    vetoed = models.BooleanField(default=False)
    commissioner_note = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self) -> str:
        return f"Trade {self.id}: {self.from_team} ↔ {self.to_team}"


class TradeItem(models.Model):
    trade = models.ForeignKey("Trade", on_delete=models.CASCADE, related_name="items")
    player = models.ForeignKey("Player", on_delete=models.CASCADE)
    from_team = models.ForeignKey("Team", on_delete=models.CASCADE, related_name="trade_items_out")
    to_team = models.ForeignKey(
        "Team",
        on_delete=models.CASCADE,
        related_name="trade_items_in",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return f"{self.player} in Trade {self.trade.id}"

