# league/apps.py
from django.apps import AppConfig


class LeagueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "league"

    def ready(self):
        # ✅ Ensures Django loads matchup models without importing them inside models.py
        import league.models_matchups  # noqa: F401
