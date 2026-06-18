import requests
from database import Session, Match
from dotenv import load_dotenv
import os
import re

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

TEAM_NAME_ALIASES = {
    "Czechia": "Czech Republic",
    "Cape Verde Islands": "Cape Verde",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "United States": "USA",
}


def get_highlightly_team_id(db_team_name):
    highlightly_name = TEAM_NAME_ALIASES.get(db_team_name, db_team_name)
    return TEAM_IDS.get(highlightly_name)


def _hl_get(endpoint, params=None):
    if not HIGHLIGHTLY_API_KEY:
        print("Missing HIGHLIGHTLY_API_KEY in environment.")
        return None
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


def _as_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []


def _first_present(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def fetch_world_cup_matches(limit=100):
    data = _hl_get("matches", {
        "leagueId": WORLD_CUP_LEAGUE_ID,
        "season": WORLD_CUP_SEASON,
        "limit": limit
    })
    return _as_list(data)


def _team_name(match, side):
    team = match.get(f"{side}Team") or match.get(side) or {}
    if isinstance(team, dict):
        return team.get("name")
    return team


def _match_status(match):
    state = match.get("state") or {}
    return match.get("status") or state.get("description") or state.get("short") or "SCHEDULED"


def _match_date(match):
    raw_date = match.get("date") or match.get("utcDate") or match.get("startTime")
    return raw_date[:10] if raw_date else None


def _score_pair(match):
    score = match.get("score")
    if isinstance(score, dict):
        full_time = score.get("fullTime") or score.get("current") or score
        if isinstance(full_time, dict):
            return full_time.get("home"), full_time.get("away")

    state_score = (match.get("state") or {}).get("score") or {}
    current = state_score.get("current")
    if isinstance(current, str):
        numbers = [int(n) for n in re.findall(r"\d+", current)]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]

    return None, None


# ── Standings from DB ──────────────────────────────────────────────

def get_group_standings(group_name, exclude_match_id=None):
    session = Session()
    query = session.query(Match).filter(
        Match.group_name == group_name,
        Match.status.in_(["FINISHED", "Finished"])
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
        if hg is None or ag is None:
            continue

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


# ── Highlightly: match lookup ──────────────────────────────────────

def find_highlightly_match_id(home_team, away_team, match_date):
    matches = fetch_world_cup_matches()
    if not matches:
        return None

    home_alias = TEAM_NAME_ALIASES.get(home_team, home_team)
    away_alias = TEAM_NAME_ALIASES.get(away_team, away_team)

    for m in matches:
        m_home = _team_name(m, "home")
        m_away = _team_name(m, "away")
        m_date = _match_date(m)

        if m_home == home_alias and m_away == away_alias and m_date == match_date:
            return m["id"]

    return None


# ── Highlightly: full match detail ────────────────────────────────

def fetch_highlightly_match(highlightly_match_id):
    data = _hl_get(f"matches/{highlightly_match_id}")
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    if isinstance(data, dict):
        return data
    return None


# ── Format helpers ─────────────────────────────────────────────────

def _event_minute(event):
    minute = _first_present(
        event.get("time"), event.get("minute"),
        event.get("minutes"), event.get("elapsed")
    )
    extra = _first_present(event.get("extraTime"), event.get("addedTime"))
    if minute is None:
        return "?"
    if extra:
        return f"{minute}+{extra}'"
    return f"{minute}'"


def _event_player(event, *keys):
    for key in keys:
        value = event.get(key)
        if isinstance(value, dict):
            return value.get("name")
        if value:
            return value
    return None


def format_match_events(match_detail):
    events = _as_list(match_detail.get("events", []))
    if not events:
        return None

    lines = []
    goals = [e for e in events if str(e.get("type", "")).lower() in ("goal", "penalty", "own goal")]
    cards = [e for e in events if "card" in str(e.get("type", "")).lower()]
    subs = [e for e in events if str(e.get("type", "")).lower() == "substitution"]

    if goals:
        lines.append("Goals:")
        for g in goals:
            team = g.get("team") or {}
            player = _event_player(g, "player", "scorer", "playerName")
            assist = _event_player(g, "assist", "assistedBy", "assistPlayer")
            assist_str = f" (assist: {assist})" if assist else ""
            lines.append(f"  {_event_minute(g)} {player} ({team.get('name')}){assist_str} [{g.get('type')}]")

    if cards:
        lines.append("\nCards:")
        for c in cards:
            team = c.get("team") or {}
            player = _event_player(c, "player", "playerName")
            lines.append(f"  {_event_minute(c)} {c.get('type')} - {player} ({team.get('name')})")

    if subs:
        lines.append("\nSubstitutions:")
        for s in subs:
            team = s.get("team") or {}
            player_on = _event_player(s, "player", "playerIn", "in")
            player_off = _event_player(s, "substituted", "playerOut", "out")
            if player_off:
                lines.append(f"  {_event_minute(s)} {player_on} replaces {player_off} ({team.get('name')})")
            else:
                lines.append(f"  {_event_minute(s)} {player_on} ({team.get('name')})")

    return "\n".join(lines) if lines else None


def format_period_scores(match_detail):
    state_score = (match_detail.get("state") or {}).get("score") or {}
    current = state_score.get("current")

    sections = []
    if current:
        sections.append(f"Full-time score: {current}")

    return "\n".join(sections) if sections else None


def format_match_statistics(match_detail):
    stats = _as_list(match_detail.get("statistics", []))
    if not stats:
        return None

    key_stats = [
        "Possession", "Expected Goals", "Shots on target", "Shots off target",
        "Big Chances Created", "Corners", "Fouls", "Yellow cards", "Red cards",
        "Goalkeeper saves", "Successful Dribbles", "Key Passes"
    ]

    lines = ["Match Statistics:"]
    for team_stats in stats:
        team_name = (team_stats.get("team") or {}).get("name", "Unknown")
        stat_rows = _as_list(team_stats.get("statistics", []))
        values = {}
        for row in stat_rows:
            name = _first_present(row.get("displayName"), row.get("name"))
            value = _first_present(row.get("value"), row.get("displayValue"))
            if name is not None and value is not None:
                values[name] = value
        row = []
        for stat_name in key_stats:
            if stat_name in values:
                val = values[stat_name]
                if stat_name == "Possession" and isinstance(val, float):
                    val = f"{round(val * 100)}%"
                row.append(f"{stat_name}: {val}")
        if row:
            lines.append(f"  {team_name} - " + ", ".join(row))

    return "\n".join(lines) if len(lines) > 1 else None


def format_lineups(match_detail):
    lineups = _as_list(match_detail.get("lineups", []))
    if not lineups:
        return None

    lines = ["Lineups:"]
    for lineup in lineups:
        team_name = (lineup.get("team") or {}).get("name", "Unknown")
        formation = lineup.get("formation")
        starters = []
        for player in _as_list(_first_present(lineup.get("startXI"), lineup.get("starters"), lineup.get("players"))):
            if isinstance(player, dict):
                name = _first_present(player.get("name"), (player.get("player") or {}).get("name"))
                if name:
                    starters.append(name)
        substitutes = []
        for player in _as_list(_first_present(lineup.get("substitutes"), lineup.get("bench"))):
            if isinstance(player, dict):
                name = _first_present(player.get("name"), (player.get("player") or {}).get("name"))
                if name:
                    substitutes.append(name)

        header = f"  {team_name}"
        if formation:
            header += f" ({formation})"
        lines.append(header)
        if starters:
            lines.append(f"    Starters: {', '.join(starters)}")
        if substitutes:
            lines.append(f"    Substitutes: {', '.join(substitutes)}")

    return "\n".join(lines) if len(lines) > 1 else None


# ── Main context builders ──────────────────────────────────────────

def get_match_context(home_team, away_team, match_date, highlightly_match_id=None):
    if not highlightly_match_id:
        highlightly_match_id = find_highlightly_match_id(home_team, away_team, match_date)

    if not highlightly_match_id:
        return None

    match_detail = fetch_highlightly_match(highlightly_match_id)
    if not match_detail:
        return None

    lines = [f"Highlightly match ID: {highlightly_match_id}"]

    venue = match_detail.get("venue")
    if venue:
        lines.append(f"Venue: {venue.get('name')}, {venue.get('city')}, {venue.get('country')}")

    referee = match_detail.get("referee")
    if referee:
        lines.append(f"Referee: {referee.get('name')} ({referee.get('nationality')})")

    score_str = format_period_scores(match_detail)
    if score_str:
        lines.append(score_str)

    events_str = format_match_events(match_detail)
    if events_str:
        lines.append(f"\n{events_str}")

    stats_str = format_match_statistics(match_detail)
    if stats_str:
        lines.append(f"\n{stats_str}")

    lineups_str = format_lineups(match_detail)
    if lineups_str:
        lines.append(f"\n{lineups_str}")

    return "\n".join(lines) if lines else None


def get_head_to_head(home_team, away_team):
    home_id = get_highlightly_team_id(home_team)
    away_id = get_highlightly_team_id(away_team)

    if not home_id or not away_id:
        return None

    matches = _as_list(_hl_get("head-2-head", {"teamIdOne": home_id, "teamIdTwo": away_id}))
    if not matches:
        return None

    lines = [f"Head-to-head history between {home_team} and {away_team}:"]
    for m in matches[:5]:
        m_home = _team_name(m, "home")
        m_away = _team_name(m, "away")
        score = (m.get("state") or {}).get("score", {}).get("current", "N/A")
        date = _match_date(m) or "Unknown date"
        round_name = m.get("round", "")
        lines.append(f"  {date} ({round_name}): {m_home} {score} {m_away}")

    return "\n".join(lines) if len(lines) > 1 else None


def get_team_tournament_form(team_name, exclude_match_id=None):
    team_id = get_highlightly_team_id(team_name)
    if not team_id:
        return None

    all_matches = fetch_world_cup_matches()
    if not all_matches:
        return None

    team_alias = TEAM_NAME_ALIASES.get(team_name, team_name)
    finished_matches = [
        m for m in all_matches
        if _match_status(m) in ("FINISHED", "Finished")
        and m.get("id") != exclude_match_id
        and (
            _team_name(m, "home") == team_alias or
            _team_name(m, "away") == team_alias or
            _team_name(m, "home") == team_name or
            _team_name(m, "away") == team_name
        )
    ]

    if not finished_matches:
        return None

    scorers = {}
    for m in finished_matches:
        detail = fetch_highlightly_match(m["id"])
        if not detail:
            continue
        for e in detail.get("events", []):
            event_team_name = (e.get("team") or {}).get("name")
            if event_team_name not in (team_name, team_alias):
                continue
            if e.get("type") in ("Goal", "Penalty") and e.get("player"):
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