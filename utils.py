import requests
from database import Session, Match
from dotenv import load_dotenv
import os
import re
import time

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

# ── In-memory cache ────────────────────────────────────────────────
_cache = {
    "world_cup_matches": None,
    "world_cup_matches_timestamp": 0,
    "match_details": {},
    "match_id_lookup": {},
    "head_to_head": {},
    "box_scores": {}
}

CACHE_TTL_SECONDS = 300


def _get_world_cup_matches():
    now = time.time()
    if _cache["world_cup_matches"] is None or (now - _cache["world_cup_matches_timestamp"]) > CACHE_TTL_SECONDS:
        _cache["world_cup_matches"] = fetch_world_cup_matches()
        _cache["world_cup_matches_timestamp"] = now
        _cache["match_id_lookup"].clear()
    return _cache["world_cup_matches"]


def _get_match_detail(highlightly_match_id):
    if highlightly_match_id in _cache["match_details"]:
        cached = _cache["match_details"][highlightly_match_id]
        if cached is not None:
            return cached
    result = fetch_highlightly_match(highlightly_match_id)
    if result is not None:
        _cache["match_details"][highlightly_match_id] = result
    return result


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
        if response.status_code == 429:
            print("⚠️  HIGHLIGHTLY RATE LIMIT HIT — daily quota exhausted. Match data will be unavailable until midnight reset.")
            return None
        elif response.status_code != 200:
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


def _display_group_name(group_name):
    if not group_name:
        return "Unknown"
    return group_name.replace("GROUP_", "Group ")


def _highlightly_name(team_name):
    return TEAM_NAME_ALIASES.get(team_name, team_name)


def _names_match(left, right):
    if not left or not right:
        return False
    return left == right or _highlightly_name(left) == _highlightly_name(right)


def _team_name_matches_any(name, teams):
    for team in teams:
        if _names_match(name, team):
            return team
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

def get_group_standings(group_name, exclude_match_id=None, up_to_date=None):
    session = Session()
    query = session.query(Match).filter(
        Match.group_name == group_name,
        Match.status.in_(["FINISHED", "Finished"])
    )
    if exclude_match_id:
        query = query.filter(Match.match_id != exclude_match_id)
    if up_to_date:
        query = query.filter(Match.match_date <= up_to_date)
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


def format_standings_for_prompt(group_name, exclude_match_id=None, up_to_date=None):
    standings = get_group_standings(group_name, exclude_match_id=exclude_match_id, up_to_date=up_to_date)

    if not standings:
        session = Session()
        query = session.query(Match).filter_by(group_name=group_name)
        if exclude_match_id:
            query = query.filter(Match.match_id != exclude_match_id)
        if up_to_date:
            query = query.filter(Match.match_date <= up_to_date)
        matches = query.all()
        session.close()

        teams = set()
        for m in matches:
            teams.add(m.home_team)
            teams.add(m.away_team)

        if not teams:
            return f"No data available for {_display_group_name(group_name)}."

        standings = [
            {"team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
             "gf": 0, "ga": 0, "gd": 0, "points": 0}
            for team in sorted(teams)
        ]

    lines = [f"Current {_display_group_name(group_name)} Standings:"]
    lines.append(f"{'Team':<25} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    lines.append("-" * 60)

    for row in standings:
        lines.append(
            f"{row['team']:<25} {row['played']:>3} {row['won']:>3} {row['drawn']:>3} {row['lost']:>3} "
            f"{row['gf']:>4} {row['ga']:>4} {row['gd']:>4} {row['points']:>4}"
        )

    return "\n".join(lines)


def format_qualification_scenarios_for_prompt(group_name, home_team, away_team, exclude_match_id=None):
    standings = get_group_standings(group_name, exclude_match_id=exclude_match_id)
    if not standings:
        return None

    rows = {row["team"]: row for row in standings}
    if home_team not in rows or away_team not in rows:
        return None

    lines = [f"Qualification picture for {_display_group_name(group_name)}:"]
    lines.append("Tournament format: 12 groups, top 2 from each group qualify automatically. 8 best third-place teams also qualify.")

    for team in (home_team, away_team):
        row = rows[team]
        played = row["played"]
        remaining = 3 - played
        pts = row["points"]
        gd = row["gd"]
        max_possible = pts + (remaining * 3)

        if pts >= 6:
            status = "ALREADY QUALIFIED for the Round of 32 (top-two spot secured)"
        elif pts == 4 and played == 2:
            status = "likely qualified but not yet mathematically confirmed (strong position)"
        elif max_possible < 4:
            status = "ELIMINATED — cannot finish in top two or realistically claim a third-place spot"
        elif max_possible < 6 and row.get("won", 0) == 0 and played == 2:
            status = "third-place route only — result here and results elsewhere must go their way"
        else:
            status = "qualification still to be decided"

        lines.append(f"  {team}: {pts} pt(s), played {played}, GD {gd} — {status}.")

        if "ALREADY QUALIFIED" not in status and "ELIMINATED" not in status:
            win_pts = pts + 3
            draw_pts = pts + 1
            lines.append(f"    Win -> {win_pts} pts. Draw -> {draw_pts} pts. Loss -> {pts} pts.")
            if gd < 0:
                lines.append(f"    Negative GD means margin of victory matters if it comes to tiebreakers.")

    lines.append("  Note: third-place qualification depends on results across all 12 groups and cannot be modelled here.")
    return "\n".join(lines)


# ── Highlightly: match lookup ──────────────────────────────────────

def find_highlightly_match_id(home_team, away_team, match_date):
    cache_key = (home_team, away_team, match_date)
    if cache_key in _cache["match_id_lookup"]:
        return _cache["match_id_lookup"][cache_key]

    matches = _get_world_cup_matches()
    if not matches:
        return None

    home_alias = _highlightly_name(home_team)
    away_alias = _highlightly_name(away_team)

    for m in matches:
        m_home = _team_name(m, "home")
        m_away = _team_name(m, "away")
        m_date = _match_date(m)

        if m_home == home_alias and m_away == away_alias and m_date == match_date:
            _cache["match_id_lookup"][cache_key] = m["id"]
            return m["id"]

    _cache["match_id_lookup"][cache_key] = None
    return None


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


def _card_kind(event):
    event_type = str(event.get("type", "")).lower()
    if "red" in event_type:
        return "Red Card"
    if "yellow" in event_type:
        return "Yellow Card"
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
            goal_type = str(g.get("type", ""))
            team_name = team.get("name")
            if goal_type.lower() == "own goal":
                lines.append(f"  {_event_minute(g)} {player} [Own Goal credited to {team_name}]")
            else:
                lines.append(f"  {_event_minute(g)} {player} ({team_name}){assist_str} [{g.get('type')}]")

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
            player_on = _event_player(s, "substituted", "playerIn", "in")
            player_off = _event_player(s, "player", "playerOut", "out")
            if player_off:
                lines.append(f"  {_event_minute(s)} SUB ON: {player_on} / SUB OFF: {player_off} ({team.get('name')})")
            else:
                lines.append(f"  {_event_minute(s)} SUB ON: {player_on} ({team.get('name')})")

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


def get_match_context(home_team, away_team, match_date, highlightly_match_id=None):
    if not highlightly_match_id:
        highlightly_match_id = find_highlightly_match_id(home_team, away_team, match_date)

    if not highlightly_match_id:
        return None

    match_detail = _get_match_detail(highlightly_match_id)
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


# ── Previous match helpers ─────────────────────────────────────────

def _get_previous_group_matches_for_teams(home_team, away_team, match_date, group_name=None, exclude_match_id=None):
    session = Session()
    query = session.query(Match).filter(Match.status.in_(["FINISHED", "Finished"]))
    if group_name:
        query = query.filter(Match.group_name == group_name)
    if match_date:
        query = query.filter(Match.match_date < match_date)
    if exclude_match_id:
        query = query.filter(Match.match_id != exclude_match_id)
    matches = query.all()
    session.close()

    teams = (home_team, away_team)
    return [
        match for match in matches
        if match.home_team in teams or match.away_team in teams
    ]


def _extract_card_events(match_detail, target_teams):
    events = _as_list(match_detail.get("events", []))
    cards = []
    for event in events:
        kind = _card_kind(event)
        if not kind:
            continue
        event_team = (event.get("team") or {}).get("name")
        canonical_team = _team_name_matches_any(event_team, target_teams)
        if not canonical_team:
            continue
        player = _event_player(event, "player", "playerName")
        if not player:
            continue
        cards.append({
            "team": canonical_team,
            "player": player,
            "kind": kind,
            "minute": _event_minute(event),
        })
    return cards


def get_discipline_watch(home_team, away_team, match_date, group_name=None, exclude_match_id=None):
    target_teams = (home_team, away_team)
    previous_matches = _get_previous_group_matches_for_teams(
        home_team, away_team, match_date,
        group_name=group_name,
        exclude_match_id=exclude_match_id,
    )
    if not previous_matches:
        return None

    watch = {
        team: {"yellow_counts": {}, "yellow_details": {}, "suspended": {}}
        for team in target_teams
    }
    latest_match_by_team = {}
    cards_by_match = {}

    for match in sorted(previous_matches, key=lambda m: (m.match_date or "", m.match_id or 0)):
        highlightly_id = find_highlightly_match_id(match.home_team, match.away_team, match.match_date)
        if not highlightly_id:
            continue
        detail = _get_match_detail(highlightly_id)
        if not detail:
            continue

        cards = _extract_card_events(detail, target_teams)
        cards_by_match[match.match_id] = cards
        for team in target_teams:
            if match.home_team == team or match.away_team == team:
                latest_match_by_team[team] = match

        for card in cards:
            team = card["team"]
            player = card["player"]
            if card["kind"] == "Yellow Card":
                watch[team]["yellow_counts"][player] = watch[team]["yellow_counts"].get(player, 0) + 1
                watch[team]["yellow_details"].setdefault(player, []).append(
                    f"{card['minute']} vs {match.away_team if match.home_team == team else match.home_team}"
                )

    for team in target_teams:
        latest = latest_match_by_team.get(team)
        if not latest:
            continue
        latest_cards = cards_by_match.get(latest.match_id, [])
        opponent = latest.away_team if latest.home_team == team else latest.home_team
        for card in latest_cards:
            if card["team"] != team:
                continue
            if card["kind"] == "Red Card":
                watch[team]["suspended"][card["player"]] = f"red card vs {opponent}"

        for player, count in watch[team]["yellow_counts"].items():
            if count >= 2 and player not in watch[team]["suspended"]:
                watch[team]["suspended"][player] = "two tournament yellow cards"

    return watch


def format_discipline_watch_for_prompt(home_team, away_team, match_date, group_name=None, exclude_match_id=None):
    watch = get_discipline_watch(
        home_team, away_team, match_date,
        group_name=group_name,
        exclude_match_id=exclude_match_id,
    )
    if not watch:
        return None

    lines = [
        "Discipline watch based on previous group-stage matches:",
        "Tournament rule used here: a red card means suspension for the next match; two tournament yellow cards mean suspension for the next match.",
    ]
    has_any = False

    for team in (home_team, away_team):
        team_watch = watch.get(team, {})
        suspended = team_watch.get("suspended", {})
        yellow_counts = team_watch.get("yellow_counts", {})

        lines.append(f"  {team}:")
        if suspended:
            has_any = True
            for player, reason in suspended.items():
                lines.append(f"    Suspended: {player} ({reason})")
        else:
            lines.append("    Suspended: none found in available card data")

        at_risk = [
            player for player, count in yellow_counts.items()
            if count == 1 and player not in suspended
        ]
        if at_risk:
            has_any = True
            lines.append(f"    One yellow from suspension: {', '.join(sorted(at_risk))}")
        else:
            lines.append("    One yellow from suspension: none found in available card data")

    return "\n".join(lines) if has_any else None


def format_recent_match_context_for_prompt(home_team, away_team, match_date, group_name=None, exclude_match_id=None):
    previous_matches = _get_previous_group_matches_for_teams(
        home_team, away_team, match_date,
        group_name=group_name,
        exclude_match_id=exclude_match_id,
    )
    if not previous_matches:
        return None

    latest_by_team = {}
    for match in sorted(previous_matches, key=lambda m: (m.match_date or "", m.match_id or 0)):
        for team in (home_team, away_team):
            if match.home_team == team or match.away_team == team:
                latest_by_team[team] = match

    lines = ["Most recent group match for each team:"]
    found = False
    for team in (home_team, away_team):
        match = latest_by_team.get(team)
        if not match:
            continue
        opponent = match.away_team if match.home_team == team else match.home_team
        team_score = match.home_score if match.home_team == team else match.away_score
        opp_score = match.away_score if match.home_team == team else match.home_score
        if team_score is None or opp_score is None:
            result_text = f"vs {opponent}, final score unavailable"
        elif team_score > opp_score:
            result_text = f"beat {opponent} {team_score}-{opp_score}"
        elif team_score < opp_score:
            result_text = f"lost to {opponent} {team_score}-{opp_score}"
        else:
            result_text = f"drew with {opponent} {team_score}-{opp_score}"
        lines.append(f"  {team}: {result_text} on {match.match_date}.")
        found = True

    return "\n".join(lines) if found else None


def get_head_to_head(home_team, away_team):
    from datetime import date as date_today
    cache_key = (home_team, away_team)
    reverse_key = (away_team, home_team)

    if cache_key in _cache["head_to_head"]:
        return _cache["head_to_head"][cache_key]
    if reverse_key in _cache["head_to_head"]:
        return _cache["head_to_head"][reverse_key]

    home_id = get_highlightly_team_id(home_team)
    away_id = get_highlightly_team_id(away_team)

    if not home_id or not away_id:
        _cache["head_to_head"][cache_key] = None
        return None

    matches = _as_list(_hl_get("head-2-head", {"teamIdOne": home_id, "teamIdTwo": away_id}))

    if not matches:
        _cache["head_to_head"][cache_key] = None
        return None

    today = str(date_today.today())
    finished = [
        m for m in matches
        if _match_status(m) in ("Finished", "FINISHED")
        and _match_date(m) is not None
        and _match_date(m) < today
    ]

    if not finished:
        _cache["head_to_head"][cache_key] = None
        return None

    lines = [f"Head-to-head history between {home_team} and {away_team}:"]
    for m in finished[:5]:
        m_home = _team_name(m, "home")
        m_away = _team_name(m, "away")
        score = (m.get("state") or {}).get("score", {}).get("current", "N/A")
        date = _match_date(m) or "Unknown date"
        round_name = m.get("round", "")
        lines.append(f"  {date} ({round_name}): {m_home} {score} {m_away}")

    result = "\n".join(lines) if len(lines) > 1 else None
    _cache["head_to_head"][cache_key] = result
    return result


def get_team_tournament_form(team_name, exclude_match_id=None):
    team_id = get_highlightly_team_id(team_name)
    if not team_id:
        return None

    all_matches = _get_world_cup_matches()
    if not all_matches:
        return None

    team_alias = _highlightly_name(team_name)
    finished_matches = [
        m for m in all_matches
        if _match_status(m) in ("FINISHED", "Finished")
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
        detail = _get_match_detail(m["id"])
        if not detail:
            continue
        for e in _as_list(detail.get("events", [])):
            event_team_name = (e.get("team") or {}).get("name")
            if event_team_name not in (team_name, team_alias):
                continue
            event_type = str(e.get("type", ""))
            player = _event_player(e, "player", "scorer", "playerName")
            assist = _event_player(e, "assist", "assistedBy", "assistPlayer")
            if event_type in ("Goal", "Penalty") and player:
                scorers.setdefault(player, {"goals": 0, "assists": 0})
                scorers[player]["goals"] += 1
                if assist:
                    scorers.setdefault(assist, {"goals": 0, "assists": 0})
                    scorers[assist]["assists"] += 1

    if not scorers:
        return None

    lines = [f"{team_name} - cumulative goal involvements across all tournament matches so far (not match-specific):"]
    for player, tally in scorers.items():
        parts = []
        if tally["goals"]:
            parts.append(f"{tally['goals']} goal(s)")
        if tally["assists"]:
            parts.append(f"{tally['assists']} assist(s)")
        lines.append(f"  {player}: {', '.join(parts)}")

    return "\n".join(lines)

def fetch_box_score(highlightly_match_id):
    if highlightly_match_id in _cache["box_scores"]:
        cached = _cache["box_scores"][highlightly_match_id]
        if cached is not None:
            return cached
    data = _hl_get(f"box-score/{highlightly_match_id}")
    result = _as_list(data)
    if result:
        _cache["box_scores"][highlightly_match_id] = result
    return result

def format_box_score_for_prompt(box_score_data, home_team, away_team):
    if not box_score_data:
        return None
    
    lines = ["Player Box Scores (top performers highlighted):"]
    
    for team_data in box_score_data:
        team_name = (team_data.get("team") or {}).get("name", "Unknown")
        players = _as_list(team_data.get("players", []))
        
        # Filter to players who actually played
        active = [p for p in players if (p.get("minutesPlayed") or 0) > 0]
        if not active:
            continue
        
        lines.append(f"\n{team_name}:")
        
        for p in active:
            name = p.get("name") or p.get("fullName", "Unknown")
            rating = p.get("matchRating", "N/A")
            position = p.get("position", "")
            mins = p.get("minutesPlayed", 0)
            is_sub = p.get("isSubstitute", False)
            stats_list = _as_list(p.get("statistics"))
            stats = stats_list[0] if stats_list else {}
            
            goals = stats.get("goalsScored", 0)
            assists = stats.get("assists", 0)
            xg = stats.get("expectedGoals", 0)
            xa = stats.get("expectedAssists", 0)
            shots = stats.get("shotsTotal", 0)
            shots_ot = stats.get("shotsOnTarget", 0)
            key_passes = stats.get("passesKey", 0)
            pass_acc = stats.get("passesAccuracy", "")
            tackles = stats.get("tacklesTotal", 0)
            intercepts = stats.get("interceptionsTotal", 0)
            rating_val = float(rating) if rating and rating != "N/A" else 0
            
            # Only include notable players (rating >= 7 or scored/assisted or high xG)
            if rating_val < 7.0 and goals == 0 and assists == 0 and xg < 0.3:
                continue
            
            sub_str = " (sub)" if is_sub else ""
            line = f"  {name} [{position}{sub_str}, {mins}', Rating: {rating}]"
            
            stats_parts = []
            if goals: stats_parts.append(f"{goals} goal(s)")
            if assists: stats_parts.append(f"{assists} assist(s)")
            if xg: stats_parts.append(f"xG: {xg:.2f}")
            if xa: stats_parts.append(f"xA: {xa:.2f}")
            if shots: stats_parts.append(f"shots: {shots_ot}/{shots} on target")
            if key_passes: stats_parts.append(f"key passes: {key_passes}")
            if pass_acc: stats_parts.append(f"pass acc: {pass_acc}")
            if tackles or intercepts: stats_parts.append(f"tackles/intercepts: {tackles}/{intercepts}")
            
            if stats_parts:
                line += " — " + ", ".join(stats_parts)
            lines.append(line)
    
    return "\n".join(lines) if len(lines) > 1 else None

def _team_standout_performer(box_score_data, team_name):
    if not box_score_data:
        return None

    best = None
    best_rating = -1.0

    for team_data in box_score_data:
        t_name = (team_data.get("team") or {}).get("name", "")
        if not _names_match(t_name, team_name):
            continue
        players = _as_list(team_data.get("players", []))
        active = [p for p in players if (p.get("minutesPlayed") or 0) > 0]
        for p in active:
            try:
                rating_val = float(p.get("matchRating"))
            except (TypeError, ValueError):
                rating_val = 0.0
            if rating_val > best_rating:
                best_rating = rating_val
                best = p

    if not best or best_rating <= 0:
        return None

    name = best.get("name") or best.get("fullName", "Unknown")
    stats_list = _as_list(best.get("statistics"))
    stats = stats_list[0] if stats_list else {}
    goals = stats.get("goalsScored", 0)
    assists = stats.get("assists", 0)

    parts = [f"rating {best_rating:.1f}"]
    if goals:
        parts.append(f"{goals} goal(s)")
    if assists:
        parts.append(f"{assists} assist(s)")

    return f"{name} ({', '.join(parts)})"


def format_recent_standout_performers_for_prompt(home_team, away_team, match_date, group_name=None, exclude_match_id=None):
    previous_matches = _get_previous_group_matches_for_teams(
        home_team, away_team, match_date,
        group_name=group_name,
        exclude_match_id=exclude_match_id,
    )
    if not previous_matches:
        return None

    latest_by_team = {}
    for match in sorted(previous_matches, key=lambda m: (m.match_date or "", m.match_id or 0)):
        for team in (home_team, away_team):
            if match.home_team == team or match.away_team == team:
                latest_by_team[team] = match

    lines = ["Standout performer from each team's most recent match (match-specific, not tournament totals):"]
    found = False

    for team in (home_team, away_team):
        match = latest_by_team.get(team)
        if not match:
            continue
        highlightly_id = find_highlightly_match_id(match.home_team, match.away_team, match.match_date)
        if not highlightly_id:
            continue
        box_score_data = fetch_box_score(highlightly_id)
        standout = _team_standout_performer(box_score_data, team)
        if standout:
            lines.append(f"  {team}: {standout}")
            found = True

    return "\n".join(lines) if found else None

def fetch_player_summary(player_name):
    # Search by name
    data = _hl_get("players", {"name": player_name, "limit": 5})
    players = _as_list(data)
    
    if not players:
        return None
    
    # Take first match
    player = players[0]
    player_id = player.get("id")
    if not player_id:
        return None
    
    # Fetch full summary
    summary_data = _hl_get(f"players/{player_id}")
    summary = _as_list(summary_data)
    summary = summary[0] if summary else {}
    
    # Fetch career stats
    stats_data = _hl_get(f"players/{player_id}/statistics")
    stats = _as_list(stats_data)
    stats = stats[0] if stats else {}
    
    return {
        "id": player_id,
        "name": summary.get("name", player_name),
        "profile": summary.get("profile", {}),
        "perCompetition": stats.get("perCompetition", []),
        "perClub": stats.get("perClub", [])
    }
