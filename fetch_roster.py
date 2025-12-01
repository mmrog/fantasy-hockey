from nhlpy import NHLClient
import pprint

SEASON = "20242025"

def main():
    client = NHLClient()

    teams = client.teams.teams()
    team = teams[0]

    print("Using team:", team["name"], "| Abbr:", team["abbr"])

    roster = client.teams.team_roster(team["abbr"], SEASON)

    print("\nRoster groups:", roster.keys())

    all_players = roster["forwards"] + roster["defensemen"] + roster["goalies"]

    print(f"\nTotal players combined: {len(all_players)}\n")

    print("Raw example player:\n")
    pprint.pprint(all_players[0])

    print("\nFormatted roster:\n")
    for p in all_players:
        name = f"{p['firstName']['default']} {p['lastName']['default']}"
        print(f"- {name} ({p['positionCode']})  ID={p['id']}")

if __name__ == "__main__":
    main()

