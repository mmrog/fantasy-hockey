from nhlpy import NHLClient

def main():
    client = NHLClient()
    teams = client.teams.teams()

    print("NHL Teams Loaded:", len(teams))
    print()

    for t in teams[:10]:
        print(
            t["franchise_id"],
            "-",
            t["name"],
            "(" + t["abbr"] + ")",
            "- Division:",
            t["division"]["name"],
        )

if __name__ == "__main__":
    main()
