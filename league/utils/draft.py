from league.models import Draft, DraftPick, Team

def generate_draft_order(draft: Draft):
    teams = list(Team.objects.filter(league=draft.league))
    team_count = len(teams)

    picks = []
    overall = 1

    for round_num in range(1, draft.rounds + 1):

        if draft.format == "SNAKE":
            # odd rounds = 1→N, even rounds = N→1
            order = teams if round_num % 2 == 1 else list(reversed(teams))
        else:
            # straight (1→N every round)
            order = teams

        for pick_num, team in enumerate(order, start=1):
            picks.append(
                DraftPick(
                    draft=draft,
                    round_number=round_num,
                    pick_number=pick_num,
                    overall_number=overall,
                    team=team
                )
            )
            overall += 1

    DraftPick.objects.bulk_create(picks)
