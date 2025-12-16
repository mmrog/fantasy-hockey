from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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
        related_name="commissioned_leagues"
    )

    scoring_mode = models.CharField(
        max_length=10,
        choices=SCORING_MODES,
        default="FIXED"
    )

    # -------- Waiver Settings (per league) --------
    skater_waiver_hours = models.PositiveIntegerField(
        default=72,
        help_text="Waiver duration in hours for skaters."
    )
    goalie_waiver_hours = models.PositiveIntegerField(
        default=48,
        help_text="Waiver duration in hours for goalies."
    )

    # -------- Roster / Lineup Settings --------
    max_roster_size = models.PositiveIntegerField(
        default=20,
        help_text="Total max players on a team (including bench and IR)."
    )
    bench_slots = models.PositiveIntegerField(
        default=3,
        help_text="Number of bench slots per team."
    )
    ir_slots = models.PositiveIntegerField(
        default=2,
        help_text="Number of IR slots per team."
    )

    # -------- Daily Lineup Lock Time --------
    lock_hour = models.PositiveSmallIntegerField(
        default=17,
        help_text="Hour of day (0–23) when daily lineups lock."
    )
    lock_minute = models.PositiveSmallIntegerField(
        default=0,
        help_text="Minute of hour (0–59) when daily lineups lock."
    )

    def __str__(self):
        return f"{self.name} ({self.season_year})"


class LeagueRole(models.Model):
    ROLE_CHOICES = [
        ("COMMISSIONER", "Commissioner"),
        ("CO_COMMISSIONER", "Co-Commissioner"),
        ("MANAGER", "Manager"),
    ]

    league = models.ForeignKey(League, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("league", "user")

    def __str__(self):
        return f"{self.user.username} — {self.role}"


# ================================================================
# PLAYER POSITIONS (Independent of League)
# ================================================================

class PlayerPosition(models.Model):
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.code


# ================================================================
# LINEUP POSITIONS (Depend on League)
# ================================================================

class Position(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    code = models.CharField(max_length=10)

    allowed_player_positions = models.ManyToManyField(
        PlayerPosition,
        blank=True,
        related_name="allowed_in_positions",
    )

    class Meta:
        unique_together = ("league", "code")

    def __str__(self):
        return f"{self.code} ({self.league.name})"


# ================================================================
# DRAFT MODELS
# ================================================================

class Draft(models.Model):
    league = models.OneToOneField(League, on_delete=models.CASCADE)
    is_snake = models.BooleanField(default=True)
    time_per_pick_seconds = models.IntegerField(default=90)
    starts_at = models.DateTimeField(null=True, blank=True)
    draft_order_generated = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.league.name} Draft"


class DraftPick(models.Model):
    draft = models.ForeignKey(Draft, on_delete=models.CASCADE)
    round_number = models.IntegerField()
    pick_number = models.IntegerField()
    overall_number = models.IntegerField()
    team = models.ForeignKey("Team", on_delete=models.SET_NULL, null=True)
    player = models.ForeignKey("Player", on_delete=models.SET_NULL, null=True, blank=True)
    is_selected = models.BooleanField(default=False)

    def __str__(self):
        return f"Round {self.round_number}, Pick {self.pick_number}"


class DraftOrder(models.Model):
    draft = models.ForeignKey(Draft, on_delete=models.CASCADE)
    position = models.IntegerField()
    team = models.ForeignKey("Team", on_delete=models.CASCADE)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.draft} — {self.position}: {self.team}"


# ================================================================
# TEAMS
# ================================================================

class Team(models.Model):
    name = models.CharField(max_length=100)
    league = models.ForeignKey(League, on_delete=models.CASCADE)

    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="managed_teams",
    )

    def __str__(self):
        return f"{self.name} ({self.league.name})"


# ================================================================
# NHL PLAYER
# ================================================================

class Player(models.Model):
    nhl_id = models.IntegerField(unique=True, null=True, blank=True)
    is_exception = models.BooleanField(default=False)

    # Identity
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    full_name = models.CharField(max_length=100)

    # PlayerPosition FK
    position = models.ForeignKey(PlayerPosition, on_delete=models.CASCADE)

    shoots = models.CharField(max_length=1, null=True, blank=True)
    number = models.IntegerField(null=True, blank=True)
    headshot = models.URLField(null=True, blank=True)

    # Waivers
    on_waivers = models.BooleanField(default=False)
    waiver_expires = models.DateTimeField(null=True, blank=True)

    # NHL stats
    games_played = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    plus_minus = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)
    hits = models.IntegerField(default=0)

    # Fantasy scoring
    fantasy_score = models.FloatField(default=0)

    # Injuries
    injured = models.BooleanField(default=False)
    injury_note = models.CharField(max_length=100, null=True, blank=True)

    updated = models.DateTimeField(auto_now=True)

    @property
    def is_goalie(self):
        return self.position.code == "G"

    def update_fantasy_score(self, league):
        from league.utils.scoring import calculate_player_score
        self.fantasy_score = calculate_player_score(self, league)
        self.save(update_fields=["fantasy_score"])

    def __str__(self):
        return f"{self.full_name} ({self.position.code})"


# ================================================================
# ROSTERS
# ================================================================

class Roster(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("team", "player")

    def __str__(self):
        return f"{self.team} — {self.player}"


# ================================================================
# DAILY LINEUPS
# ================================================================

class DailyLineup(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        unique_together = ("team", "date")

    def __str__(self):
        return f"{self.team.name} — {self.date}"


class DailySlot(models.Model):
    lineup = models.ForeignKey(DailyLineup, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    slot = models.ForeignKey(Position, on_delete=models.CASCADE)

    def clean(self):
        # Check player fits the slot position rules
        if self.player:
            player_fits_slot(self.player, self.slot)

        # Ensure slot is not used twice in same lineup
        if DailySlot.objects.filter(
            lineup=self.lineup,
            slot=self.slot
        ).exclude(id=self.id).exists():
            raise ValidationError(f"Slot {self.slot.code} already assigned.")

        # Ensure player is on this team's roster
        if self.player and not Roster.objects.filter(
            team=self.lineup.team,
            player=self.player
        ).exists():
            raise ValidationError(
                f"{self.player.full_name} is not on this team's roster."
            )

    class Meta:
        unique_together = ("lineup", "slot")

    def __str__(self):
        return f"{self.lineup.date} — {self.slot.code}"


# ================================================================
# SCORING CATEGORIES
# ================================================================

class ScoringCategory(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    stat_key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)

    class Meta:
        unique_together = ("league", "stat_key")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.league.name}"


# ================================================================
# LEAGUE SETTINGS (extra knobs)
# ================================================================

class LeagueSettings(models.Model):
    league = models.OneToOneField(League, on_delete=models.CASCADE)

    # Waivers (note: also stored on League; we can consolidate later)
    goalie_waiver_hours = models.IntegerField(default=48)
    skater_waiver_hours = models.IntegerField(default=72)

    # Limits
    weekly_move_limit = models.IntegerField(default=4)
    goalie_min_games = models.IntegerField(default=3)

    # Lineup slot counts
    slots_c = models.IntegerField(default=2)
    slots_lw = models.IntegerField(default=2)
    slots_rw = models.IntegerField(default=2)
    slots_f = models.IntegerField(default=1)
    slots_d = models.IntegerField(default=4)
    slots_g = models.IntegerField(default=2)
    slots_bn = models.IntegerField(default=3)
    slots_ir = models.IntegerField(default=2)

    def __str__(self):
        return f"Settings for {self.league.name}"


# ================================================================
# ADVANCED STATS
# ================================================================

class PlayerAdvancedStats(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
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

    def __str__(self):
        return f"{self.player.full_name} Advanced Stats ({self.season})"


# ================================================================
# TRANSACTIONS
# ================================================================

class Transaction(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)

    action = models.CharField(max_length=50)
    # Examples: "ADD", "DROP", "TRADE", "MOVE_TO_IR", "MOVE_TO_BENCH", "COMMISSIONER_EDIT"

    note = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} — {self.player} ({self.created_at})"


# ================================================================
# TRADES
# ================================================================

class Trade(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    from_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="trades_sent"
    )
    to_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="trades_received"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    vetoed = models.BooleanField(default=False)
    commissioner_note = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Trade {self.id}: {self.from_team} ↔ {self.to_team}"


class TradeItem(models.Model):
    trade = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name="items"
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    from_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="trade_items_out"
    )
    to_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="trade_items_in",
        null=True,
        blank=True,
    )

    

    def __str__(self):
        return f"{self.player} in Trade {self.trade.id}"
