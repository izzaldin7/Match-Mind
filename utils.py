from database import Session, Match

def get_group_standings(group_name):
    session = Session()
    matches = session.query(Match).filter_by(
        group_name = group_name,
        status = "FINISHED"
    ).all()
    session.close()

    if not matches:
        return None
    
    standings = {}

    for match in matches:
        home = match.home_team
        away = match.away_team
        hg = match.home_score
        ag = match.away_score

        #Initialize teams if not seen yet
        for team in [home, away]:
            if team not in standings:
                standings[team] = {
                    "team": team,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals for": 0,
                    "goals against": 0,
                    "goal difference": 0,
                    "points": 0
                }

        #Update stats
        standings[home]["played"] += 1
        standings[away]["played"] += 1
        standings[home]["gf"] += hg
        standings[home]["ga"] += ag
        standings[away]["gf"] += ag
        standings[away]["ga"] += hg

        if hg > ag:
            standings[home]["won"] += 1
            standings[away]["lost"] += 1
            standings[home]["points"] += 3

        elif ag > hg:
            standings[away]["won"] += 1
            standings[home]["lost"] += 1
            standings[away]["points"] += 3

        else:
            standings[home]["drawn"] += 1
            standings[away]["drawn"] += 1
            standings[home]["points"] += 1
            standings[away]["points"] += 1

    #Calculate GD and sort
    for team in standings:
        standings[team]["gd"] = standings[team]["gf"] - standings[team]["ga"]

    sorted_standings = sorted(
        standings.values(),
        key = lambda x: (x["points"], x["gd"], x["gf"]),
        reverse = True
    )

    return sorted_standings

def format_standings_for_prompt(group_name):
    standings = get_group_standings(group_name)

    if not standings:
        session = Session()
        matches = session.query(Match).filter_by(group_name=group_name).all()
        session.close()

        teams = set()
        for m in matches:
            teams.add(m.home_team)
            teams.add(m.away_team)

        if not teams:
            return f"No data available for Group {group_name}."
        
        standings = [
            {"team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
             "gf": 0, "ga": 0, "gd": 0, "points": 0}
             for team in sorted(teams)
        ]

    lines = [f"Current Group {group_name} Standings:"]
    lines.append(f"{'Team':<25} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    lines.append("-" * 60)

    for row in standings:
        lines.append(
            f"{row['team']:<25} {row['played']:>3} {row['won']:>3} {row['drawn']:>3} {row['lost']:>3} "
            f"{row['gf']:>4} {row['ga']:>4} {row['gd']:>4} {row['points']:>4}"
        )

    return "\n".join(lines)

        