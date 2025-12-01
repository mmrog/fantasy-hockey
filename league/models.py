from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .validators import player_fits_slot


# ================================================================
# DYNAMIC POSITIONS
# ================================================================

class PlayerPosition(models.Model):
    """
    NHL Positions (C, LW, RW, D, G)
    Commissioner can add/remove these.
    """
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.code


class Position(models.Model):
    """
    Lineup Slots (C, LW, RW, F, D, G, BN, IR)
    Commissioner controls allowed player positions.
    """
    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=100, blank=True)

    # PlayerPositions allowed in this slot
    allowed_player_positions = models.ManyToManyField(
        PlayerPosition,
        related_name="valid_lineup_slots",
        blank=True
    )

    is_lineup_slot = models.BooleanField(default=True)

    def __str__(self):
        return self.code


# ================================================================
# LEAGUE + ROLES
# ================================================================

class League(models.Model):
    SCORING_MODES = [
        ("FIXED", "Fixed"),
        ("CUSTOM", "Custom (Commissioner Editable)")
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
# TEAMS
# ================================================================

class Team(models.Model):
    name = models.CharField(max_length=100)
    league = models.ForeignKey(League, on_delete=models.CASCADE)

    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="managed_teams"
    )

    def __str__(self):
        return f"{self.name} ({self.league.name})"


# ================================================================
# NHL PLAYER
# ================================================================

class Player(models.Model):
    """
    NHL Player - dynamic position tied to PlayerPosition
    """

    nhl_id = models.IntegerField(unique=True)

    # Identity
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    full_name = models.CharField(max_length=100)

    # Dynamic position (C, LW, RW, D, G)
    position = models.ForeignKey(PlayerPosition, on_delete=models.CASCADE)

    shoots = models.CharField(max_length=1, null=True, blank=True)
    number = models.IntegerField(null=True, blank=True)
    headshot = models.URLField(null=True, blank=True)

    # Fantasy metadata
    on_waivers = models.BooleanField(default=False)
    waiver_expires = models.DateTimeField(null=True, blank=True)

    # Stats
    games_played = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    plus_minus = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)
    hits = models.IntegerField(default=0)

    fantasy_score = models.FloatField(default=0)
    updated = models.DateTimeField(auto_now=True)

    @property
    def is_goalie(self):
        return self.position.code == "G"

    def __str__(self):
        return f"{self.full_name} ({self.position.code})"


# ================================================================
# ROSTER OWNERSHIP
# ================================================================

class Roster(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("team", "player")


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
    """
    One lineup slot for a given day.
    """

    lineup = models.ForeignKey(DailyLineup, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    slot = models.ForeignKey(Position, on_delete=models.CASCADE)

    def clean(self):
        # Validate slot compatibility
        if self.player:
            player_fits_slot(self.player, self.slot)

        # Block duplicate slot types
        if DailySlot.objects.filter(
            lineup=self.lineup,
            slot=self.slot
        ).exclude(id=self.id).exists():
            raise ValidationError(f"Slot {self.slot.code} already assigned.")

        # Player must belong to team
        if self.player:
            if not Roster.objects.filter(
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
    stat_key = models.CharField(max_length=50)  # goals, assists, etc.
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)

    class Meta:
        unique_together = ("league", "stat_key")

    def __str__(self):
        return f"{self.name} ({self.league.name})"
