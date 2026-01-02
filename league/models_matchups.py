# league/models_matchups.py
from django.db import models


class Matchup(models.Model):
    league = models.ForeignKey("league.League", on_delete=models.CASCADE)
    date = models.DateField()

    home_team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="home_matchups")
    away_team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="away_matchups")

    processed = models.BooleanField(default=False)

    class Meta:
        unique_together = ("league", "date", "home_team", "away_team")

    def __str__(self):
        return f"{self.league.name} {self.date}: {self.home_team} vs {self.away_team}"


class TeamCategoryTotal(models.Model):
    league = models.ForeignKey("league.League", on_delete=models.CASCADE)
    team = models.ForeignKey("league.Team", on_delete=models.CASCADE)
    date = models.DateField()
    category = models.ForeignKey("league.ScoringCategory", on_delete=models.CASCADE)
    value = models.FloatField(default=0)

    class Meta:
        unique_together = ("team", "date", "category")


class MatchupCategoryResult(models.Model):
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE, related_name="category_results")
    category = models.ForeignKey("league.ScoringCategory", on_delete=models.CASCADE)

    home_value = models.FloatField(default=0)
    away_value = models.FloatField(default=0)

    winner = models.CharField(
        max_length=10,
        choices=[("HOME", "Home"), ("AWAY", "Away"), ("TIE", "Tie")],
        default="TIE",
    )

    class Meta:
        unique_together = ("matchup", "category")
