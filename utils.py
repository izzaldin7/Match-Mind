import requests
from database import Session, Match
from dotenv import load_dotenv
import os

load_dotenv()

HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY")
HIGHLIGHTLY_HEADERS = {"x-rapidapi-key": HIGHLIGHTLY_API_KEY}
HIGHLIGHTLY_BASE = "https://soccer.highlightly.net"
WORLD_CUP_LEAGUE_ID = 1635
WORLD_CUP_SEASON = 2026

TEAM_IDS = {
    "Algeria": 1304516, "Austria": 660309, "Jordan": 1318132, "Argentina": 22910,
    "Congo DR": 1284092, "Uzbekistan": 1335152, "Colombia": 7592, "Portugal": 23761,
    "Croatia": 3337, "Ghana": 1280688, "Panama": 10145, "England": 9294,
    "Egypt": 28016, "Iran": 19506, "New Zealand": 3977507, "Belgium": 1635,
    "Uruguay": 6741, "Spain": 8443, "Cape Verde": 1305367, "Saudi Arabia": 20357,
    "Norway": 928374, "France": 2486, "Senegal": 11847, "Iraq": 1334301,
    "Turkey": 662011, "USA": 2029568, "Paraguay": 2026164, "Australia": 17804,
    "Tunisia": 24612, "Netherlands": 952202, "Japan": 10996, "Sweden": 5039,
    "Ecuador": 2027866, "Germany": 22059, "Curaçao": 4706814, "Ivory Coast": 1278135,
    "South Africa": 1303665, "South Korea": 15251, "Czech Republic": 656054,
    "Mexico": 14400, "Morocco": 27165, "Haiti": 2031270, "Scotland": 943692,
    "Brazil": 5890, "Bosnia & Herzegovina": 947947, "Qatar": 1336003,
    "Switzerland": 13549, "Canada": 4705963
}

# Maps your DB's naming (from football-data.org) to Highlightly's naming
TEAM_NAME_ALIASES = {
    "Czechia": "Czech Republic",
    "Cape Verde Islands": "Cape Verde",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "United States": "USA",
}


def get_highlightly_team_id(db_team_name):
    """
    Resolves a team name (as stored in your DB) to its Highlightly team ID,
    accounting for naming differences between data sources.
    """
    highlightly_name = TEAM_NAME_ALIASES.get(db_team_name, db_team_name)
    return TEAM_IDS.get(highlightly_name)


def _hl_get(endpoint, params=None):
    """Internal helper for GET requests to Highlightly, with basic error handling."""
    try:
        url = f"{HIGHLIGHTLY_BASE}/{endpoint}"
        response = requests.get(url, headers=HIGHLIGHTLY_HEADERS, params=params, timeout=10)
        if response.status_code != 200:
            print(f"Highlightly request failed [{endpoint}]: {response.status_code}")
            return None
        return response.json()
    except Exception as e:
        print(f"Highlightly request error [{endpoint}]: {e}")
        return None


# ── Standings from DB (unchanged, still reliable) ──────────────────

def get_group_standings(group_name, exclude_match_id=None):
    session = Session()
    query = session.query(Match).filter_by(
        group_name=group_name,
        status="FINISHED"
    )
    if exclude_match_id:
        query = query.filter(Match.match_id != exclude_match_id)
    matches = query.all()
    session.close()

    if not matches:
        return None

    standings = {}

    for match in matches:
        home = match.home_team
        away = match.away_team
        hg = match.home_score
        ag = match.away_score

        for team in [home, away]:
            if team not in standings:
                standings[team] = {
                    "team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
                    "gf": 0, "ga": 0, "gd": 0, "points": 0
                }

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

    for team in standings:
        standings[team]["gd"] = standings[team]["gf"] - standings[team]["ga"]

    return sorted(standings.values(), key=lambda x: (x["points"], x["gd"], x["gf"]), reverse=True)


def format_standings_for_prompt(group_name, exclude_match_id=None):
    standings = get_group_standings(group_name, exclude_match_id=exclude_match_id)

    if not standings:
        session = Session()
        query = session.query(Match).filter_by(group_name=group_name)
        if exclude_match_id:
            query = query.filter(Match.match_id != exclude_match_id)
        matches = query.all()
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


# ── Highlightly: match lookup ────────────────────────────────────

def find_highlightly_match_id(home_team, away_team, match_date):
    """
    Finds the Highlightly match ID for a given fixture by team names and date.
    match_date should be 'YYYY-MM-DD' as stored in your DB.
    """
    data = _hl_get("matches", {
        "leagueId": WORLD_CUP_LEAGUE_ID,
        "season": WORLD_CUP_SEASON,
        "limit": 100
    })
    if not data:
        return None

    home_alias = TEAM_NAME_ALIASES.get(home_team, home_team)
    away_alias = TEAM_NAME_ALIASES.get(away_team, away_team)

    for m in data.get("data", []):
        m_home = m["homeTeam"]["name"]
        m_away = m["awayTeam"]["name"]
        m_date = m["date"][:10]

        if m_home == home_alias and m_away == away_alias and m_date == match_date:
            return m["id"]

    return None


# ── Highlightly: full match detail (events, stats, referee, venue) ─

def fetch_highlightly_match(highlightly_match_id):
    """
    Fetches full match detail from Highlightly: venue, referee, events
    (goals, cards, substitutions), and team statistics.
    """
    data = _hl_get(f"matches/{highlightly_match_id}")
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    return data[0]


def format_match_events(match_detail):
    """
    Formats goals, cards, and substitutions from a Highlightly match
    detail object into a clean string for AI prompts.
    """
    events = match_detail.get("events", [])
    if not events:
        return None

    lines = []
    goals = [e for e in events if e["type"] in ("Goal", "Penalty", "Own Goal")]
    cards = [e for e in events if e["type"] in ("Yellow Card", "Red Card")]
    subs = [e for e in events if e["type"] == "Substitution"]

    if goals:
        lines.append("Goals:")
        for g in goals:
            assist_str = f" (assist: {g['assist']})" if g.get("assist") else ""
            lines.append(f"  {g['time']}' {g['player']} ({g['team']['name']}){assist_str} [{g['type']}]")

    if cards:
        lines.append("\nCards:")
        for c in cards:
            lines.append(f"  {c['time']}' {c['type']} - {c['player']} ({c['team']['name']})")

    if subs:
        lines.append("\nSubstitutions:")
        for s in subs:
            lines.append(f"  {s['time']}' {s['player']} replaces {s['substituted']} ({s['team']['name']})")

    return "\n".join(lines) if lines else None


def format_match_statistics(match_detail):
    """
    Formats team statistics (possession, shots, xG, etc.) from a Highlightly
    match detail object into a clean string for AI prompts.
    """
    stats = match_detail.get("statistics", [])
    if not stats or len(stats) < 2:
        return None

    key_stats = [
        "Possession", "Expected Goals", "Shots on target", "Shots off target",
        "Big Chances Created", "Corners", "Fouls", "Yellow cards", "Red cards",
        "Goalkeeper saves", "Successful Dribbles", "Key Passes"
    ]

    lines = ["Match Statistics:"]
    for team_stats in stats:
        team_name = team_stats["team"]["name"]
        values = {s["displayName"]: s["value"] for s in team_stats.get("statistics", [])}
        row = []
        for stat_name in key_stats:
            if stat_name in values:
                val = values[stat_name]
                if stat_name == "Possession":
                    val = f"{round(val * 100)}%"
                row.append(f"{stat_name}: {val}")
        lines.append(f"  {team_name} — " + ", ".join(row))

    return "\n".join(lines)


def get_match_context(home_team, away_team, match_date, highlightly_match_id=None):
    """
    Builds the full real-data context string for post-match reports:
    venue, referee, goals/cards/subs, and team statistics, all from Highlightly.
    """
    if not highlightly_match_id:
        highlightly_match_id = find_highlightly_match_id(home_team, away_team, match_date)

    if not highlightly_match_id:
        return None

    match_detail = fetch_highlightly_match(highlightly_match_id)
    if not match_detail:
        return None

    lines = []

    venue = match_detail.get("venue")
    if venue:
        lines.append(f"Venue: {venue.get('name')}, {venue.get('city')}, {venue.get('country')}")

    referee = match_detail.get("referee")
    if referee:
        lines.append(f"Referee: {referee.get('name')} ({referee.get('nationality')})")

    events_str = format_match_events(match_detail)
    if events_str:
        lines.append(f"\n{events_str}")

    stats_str = format_match_statistics(match_detail)
    if stats_str:
        lines.append(f"\n{stats_str}")

    return "\n".join(lines) if lines else None


# ── Highlightly: head-to-head + team form for briefings ────────────

def get_head_to_head(home_team, away_team):
    """
    Fetches historical head-to-head matches between two teams from Highlightly.
    """
    home_id = get_highlightly_team_id(home_team)
    away_id = get_highlightly_team_id(away_team)

    if not home_id or not away_id:
        return None

    data = _hl_get("head-2-head", {"teamIdOne": home_id, "teamIdTwo": away_id})
    if not data:
        return None

    if not data:
        return None

    lines = [f"Head-to-head history between {home_team} and {away_team}:"]
    for m in data[:5]:
        m_home = m["homeTeam"]["name"]
        m_away = m["awayTeam"]["name"]
        score = m.get("state", {}).get("score", {}).get("current", "N/A")
        date = m["date"][:10]
        round_name = m.get("round", "")
        lines.append(f"  {date} ({round_name}): {m_home} {score} {m_away}")

    return "\n".join(lines) if len(lines) > 1 else None


def get_team_tournament_form(team_name, exclude_match_id=None):
    """
    Fetches this team's matches so far in the 2026 World Cup from Highlightly,
    and summarizes their goal involvements (scorers and assisters) across
    those matches. Used to give briefings real prior-form context.
    """
    team_id = get_highlightly_team_id(team_name)
    if not team_id:
        return None

    data = _hl_get("matches", {
        "leagueId": WORLD_CUP_LEAGUE_ID,
        "season": WORLD_CUP_SEASON,
        "teamId": team_id,
        "limit": 20
    })
    if not data:
        return None

    finished_matches = [
        m for m in data.get("data", [])
        if m.get("state", {}).get("description") == "Finished"
        and m["id"] != exclude_match_id
    ]

    if not finished_matches:
        return None

    scorers = {}
    for m in finished_matches:
        detail = fetch_highlightly_match(m["id"])
        if not detail:
            continue
        for e in detail.get("events", []):
            if e["team"]["name"] != team_name and TEAM_NAME_ALIASES.get(team_name) != e["team"]["name"]:
                continue
            if e["type"] in ("Goal", "Penalty"):
                scorers.setdefault(e["player"], {"goals": 0, "assists": 0})
                scorers[e["player"]]["goals"] += 1
                if e.get("assist"):
                    scorers.setdefault(e["assist"], {"goals": 0, "assists": 0})
                    scorers[e["assist"]]["assists"] += 1

    if not scorers:
        return None

    lines = [f"{team_name} - goal involvements so far this tournament:"]
    for player, tally in scorers.items():
        parts = []
        if tally["goals"]:
            parts.append(f"{tally['goals']} goal(s)")
        if tally["assists"]:
            parts.append(f"{tally['assists']} assist(s)")
        lines.append(f"  {player}: {', '.join(parts)}")

    return "\n".join(lines)