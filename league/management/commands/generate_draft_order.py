from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from league.models import League, Team, Draft, DraftOrder, DraftPick


class Command(BaseCommand):
    help = "Generate (or regenerate) the draft order for a league draft (snake or linear)."

    def add_arguments(self, parser):
        parser.add_argument(
            "league_id",
            type=int,
            help="League ID to generate draft order for",
        )
        parser.add_argument(
            "--seed",
            choices=["alpha", "random", "standings"],
            default="alpha",
            help="How to seed initial team order (default: alpha).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow regenerating even if draft is active or picks exist (will wipe order + picks).",
        )
        parser.add_argument(
            "--rounds",
            type=int,
            default=None,
            help="Override number of draft rounds (optional).",
        )
        parser.add_argument(
            "--type",
            choices=["SNAKE", "LINEAR"],
            default=None,
            help="Override draft type (optional).",
        )
        parser.add_argument(
            "--time-per-pick",
            type=int,
            default=None,
            help="Override time per pick in seconds (optional).",
        )

    def handle(self, *args, **options):
        league_id = options["league_id"]
        seed = options["seed"]
        force = options["force"]
        override_rounds = options["rounds"]
        override_type = options["type"]
        override_tpp = options["time_per_pick"]

        try:
            league = League.objects.get(id=league_id)
        except League.DoesNotExist:
            raise CommandError(f"League id={league_id} not found.")

        teams_qs = Team.objects.filter(league=league).select_related("manager")
        team_count = teams_qs.count()

        if team_count < 2:
            raise CommandError("Need at least 2 teams in the league to generate a draft order.")

        # Get or create draft
        draft, created = Draft.objects.get_or_create(league=league)

        # Apply overrides
        if override_rounds is not None:
            if override_rounds < 1:
                raise CommandError("--rounds must be >= 1")
            draft.rounds = override_rounds

        if override_type is not None:
            draft.draft_type = override_type

        if override_tpp is not None:
            if override_tpp < 10:
                raise CommandError("--time-per-pick must be >= 10 seconds")
            draft.time_per_pick = override_tpp

        # Safety checks
        picks_exist = DraftPick.objects.filter(draft=draft).exists()
        order_exist = DraftOrder.objects.filter(draft=draft).exists()

        if (draft.is_active or picks_exist) and not force:
            raise CommandError(
                "Draft is active or picks already exist. "
                "Use --force to wipe existing order/picks and regenerate."
            )

        # Build initial team list according to seed method
        teams = list(teams_qs)

        if seed == "alpha":
            teams.sort(key=lambda t: (t.name or "").lower())
        elif seed == "random":
            import random
            random.shuffle(teams)
        elif seed == "standings":
            # Placeholder: You can wire this up later when you track standings.
            # For now we raise a clear error so it's not silently wrong.
            raise CommandError(
                "Seed method 'standings' is not implemented yet. Use --seed alpha or --seed random."
            )

        with transaction.atomic():
            # Wipe existing (order + picks) if force or if order exists without picks
            if picks_exist or order_exist:
                DraftPick.objects.filter(draft=draft).delete()
                DraftOrder.objects.filter(draft=draft).delete()

            # Create DraftOrder rows (base order only, not repeated per round)
            DraftOrder.objects.bulk_create(
                [
                    DraftOrder(draft=draft, team=team, position=i + 1)
                    for i, team in enumerate(teams)
                ]
            )

            # Reset draft state
            draft.is_active = False
            draft.is_completed = False
            draft.current_pick = 1
            draft.started_at = None
            draft.completed_at = None
            draft.save()

        self.stdout.write(self.style.SUCCESS("Draft order generated successfully."))
        self.stdout.write(f"League: {league.name} (id={league.id})")
        self.stdout.write(f"Teams: {team_count}")
        self.stdout.write(f"Draft type: {draft.draft_type}")
        self.stdout.write(f"Rounds: {draft.rounds}")
        self.stdout.write(f"Time per pick: {draft.time_per_pick}s")
        self.stdout.write(f"Seed: {seed}")
        self.stdout.write("Order:")
        for o in DraftOrder.objects.filter(draft=draft).select_related("team").order_by("position"):
            self.stdout.write(f"  {o.position}. {o.team.name}")
