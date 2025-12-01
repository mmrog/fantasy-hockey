from nhlpy import NHLClient
import pprint

SEASON = "20242025"

def main():
    client = NHLClient()

    # Team info
    teams = client.teams.teams()
    team = teams[0]
    print("Using team:", team["name"], "| Abbr:", team["abbr"])

    # Load roster
    roster = client.teams.team_roster(team["abbr"], SEASON)

    # Flatten roster (forwards + defense + goalies)
    all_players = roster["forwards"] + roster["defensemen"] + roster["goalies"]

    # Pick one player to test
    player = all_players[0]
    pid = player["id"]
    full_name = player["firstName"]["default"] + " " + player["lastName"]["default"]

    print(f"\nFetching stats for: {full_name} (ID: {pid})")

    # Load ALL skater stats for this franchise
    stats_list = client.stats.skater_stats_summary(
        start_season=SEASON,
        end_season=SEASON,
        franchise_id=str(team["franchise_id"]),
        game_type_id=2,
        aggregate=False,
        limit=500
    )

    # Find matching player
    stat_line = None
    for row in stats_list:
        if str(row.get("playerId")) == str(pid):
            stat_line = row
            break

    if not stat_line:
        print("\n❌ No stats found for this player.")
        return

    print("\nRaw skater stats:\n")
    pprint.pprint(stat_line)

if __name__ == "__main__":
    main()
