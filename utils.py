import requests
from database import Session, Match, GeneratedContent
from dotenv import load_dotenv
import os
import re
import time
import json
from datetime import datetime, timezone

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
    "box_scores": {},
    "lineups": {}          # ← new: keyed by highlightly_match_id
}

_tournament_stats_cache = {
    "players": {},
    "teams": {},
    "matches_processed": set()
}

def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

HIGHLIGHTLY_MATCHES_TTL_SECONDS = 300
BRIEFING_CACHE_TTL_SECONDS = 60 * 60 * 2


# ── Persistent (DB-backed) cache for generated briefings/reports/lineups ──

def get_cached_content(match_id, content_type, ttl_seconds=None):
    session = Session()
    try:
        row = (
            session.query(GeneratedContent)
            .filter_by(match_id=match_id, content_type=content_type)
            .order_by(GeneratedContent.created_at.desc())
            .first()
        )
    finally:
        session.close()

    if not row:
        return None

    if ttl_seconds is not None:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created).total_seconds()
        if age > ttl_seconds:
            return None

    try:
        return json.loads(row.payload)
    except (TypeError, ValueError):
        return None


def save_cached_content(match_id, content_type, result):
    session = Session()
    try:
        session.query(GeneratedContent).filter_by(
            match_id=match_id, content_type=content_type
        ).delete()
        session.add(GeneratedContent(
            match_id=match_id,
            content_type=content_type,
            payload=json.dumps(result)
        ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_world_cup_matches():
    now = time.time()
    if _cache["world_cup_matches"] is None or (now - _cache["world_cup_matches_timestamp"]) > HIGHLIGHTLY_MATCHES_TTL_SECONDS:
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

def get_all_group_standings(exclude_match_id=None):
    session = Session()

    groups = (
        session.query(Match.group_name)
        .filter(Match.group_name.isnot(None))
        .distinct()
        .all()
    )

    session.close()

    all_groups = {}

    for (group_name,) in groups:
        standings = get_group_standings(
            group_name,
            exclude_match_id=exclude_match_id
        )

        if standings:
            all_groups[group_name] = standings

    return all_groups

def get_third_place_table(exclude_match_id=None):
    all_groups = get_all_group_standings(
        exclude_match_id=exclude_match_id
    )

    third_place_teams = []

    for group_name, standings in all_groups.items():
        if len(standings) >= 3:
            third = standings[2]

            third_place_teams.append({
                "group": group_name,
                "team": third["team"],
                "points": third["points"],
                "gd": third["gd"],
                "gf": third["gf"]
            })

    third_place_teams.sort(
        key=lambda x: (
            x["points"],
            x["gd"],
            x["gf"]
        ),
        reverse=True
    )

    return third_place_teams

def can_still_reach_best_third_place(row):
    played = row["played"]
    pts = row["points"]

    remaining = max(0, 3 - played)

    max_possible_points = pts + (remaining * 3)

    # Any team that can still reach 4+ points
    # is definitely alive in a 12-group format.
    if max_possible_points >= 4:
        return True

    # A team that can still reach 3 points
    # cannot be ruled out mathematically.
    if max_possible_points == 3:
        return True

    return False

def get_qualification_status(row):
    played = row["played"]
    pts = row["points"]

    remaining = 3 - played
    max_possible = pts + (remaining * 3)

    if pts >= 6:
        return "ALREADY QUALIFIED for the Round of 32 (top-two spot secured)"

    if pts == 4 and played == 2:
        return "likely qualified but not yet mathematically confirmed (strong position)"

    if not can_still_reach_best_third_place(row):
        return "ELIMINATED"

    if played == 2 and max_possible <= 3:
        return (
            "STILL ALIVE. Automatic qualification is no longer possible, "
            "but qualification through the best third-placed teams route "
            "remains mathematically possible."
        )

    return "qualification still to be decided"


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

        status = get_qualification_status(row)

        lines.append(f"  {team}: {pts} pt(s), played {played}, GD {gd} — {status}.")

        if "ALREADY QUALIFIED" not in status and "ELIMINATED" not in status:
            win_pts = pts + 3
            draw_pts = pts + 1
            lines.append(f"    Win -> {win_pts} pts. Draw -> {draw_pts} pts. Loss -> {pts} pts.")
            if gd < 0:
                lines.append(f"    Negative GD means margin of victory matters if it comes to tiebreakers.")

    lines.append(
    "  Note: third-place qualification is determined across all 12 groups. "
    "This analysis can identify teams still alive via the third-place route "
    "but cannot determine whether a third-placed team has mathematically "
    "secured or lost one of the eight qualifying spots."
)
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
    missed_penalties = [e for e in events if str(e.get("type", "")).lower() == "missed penalty"]
    cards = [e for e in events if "card" in str(e.get("type", "")).lower()]
    subs  = [e for e in events if str(e.get("type", "")).lower() == "substitution"]
    var_events = [e for e in events if str(e.get("type", "")).lower().startswith("var")]

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

    if missed_penalties:
        lines.append("\nMissed Penalties:")
        for mp in missed_penalties:
            team = mp.get("team") or {}
            player = _event_player(mp, "player", "scorer", "playerName")
            lines.append(f"  {_event_minute(mp)} {player} ({team.get('name')}) [Missed Penalty]")

    if var_events:
        lines.append("\nVAR Decisions:")
        for v in var_events:
            team = v.get("team") or {}
            player = _event_player(v, "player", "playerName")
            event_type = v.get("type", "VAR Decision")
            team_name = team.get("name")
            player_str = f" - {player}" if player else ""
            team_str = f" ({team_name})" if team_name else ""
            lines.append(f"  {_event_minute(v)} {event_type}{player_str}{team_str}")

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
            player_on  = _event_player(s, "substituted", "playerIn", "in")
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


# ── Lineup fetch & format ──────────────────────────────────────────

def fetch_lineup(highlightly_match_id):
    """
    Fetch lineup data from Highlightly for the given match id.
    Returns the raw dict {homeTeam: {...}, awayTeam: {...}} or None.
    Cached in _cache["lineups"] — never re-fetched once present.
    """
    if highlightly_match_id in _cache["lineups"]:
        cached = _cache["lineups"][highlightly_match_id]
        if cached is not None:
            return cached

    data = _hl_get(f"lineups/{highlightly_match_id}")

    # API returns a plain dict for lineups
    if isinstance(data, dict) and ("homeTeam" in data or "awayTeam" in data):
        _cache["lineups"][highlightly_match_id] = data
        return data

    # Sometimes wrapped in a list
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict) and ("homeTeam" in item or "awayTeam" in item):
            _cache["lineups"][highlightly_match_id] = item
            return item

    _cache["lineups"][highlightly_match_id] = None
    return None


def format_lineup_for_cache(lineup_data, home_team, away_team):
    """
    Normalise raw lineup API response into a clean dict the frontend renders.
    Returns None if no useful data is present.

    Output shape per team:
    {
        "name": "Brazil",
        "formation": "4-3-3",
        "initialLineup": [
            [{"name": "...", "number": 1, "position": "Goalkeeper"}],
            [{"name": "...", "number": 4, ...}, ...],
            ...
        ],
        "substitutes": [{"name": "...", "number": 7, "position": "..."}]
    }
    """
    if not lineup_data:
        return None

    def _normalise_team(raw, fallback_name):
        if not raw:
            return None

        # Team name: prefer explicit name field, then nested team dict, then fallback
        team_obj = raw.get("team") or {}
        team_name = (
            raw.get("name")
            if raw.get("name") and not raw.get("name", "").startswith("http")
            else team_obj.get("name") or fallback_name
        )

        players_rows = raw.get("initialLineup") or []
        normalised_rows = []
        for row in players_rows:
            if not isinstance(row, list):
                continue
            norm_row = []
            for p in row:
                if isinstance(p, dict):
                    norm_row.append({
                        "name": p.get("name") or p.get("fullName", ""),
                        "number": p.get("number") or p.get("shirtNumber"),
                        "position": p.get("position", "")
                    })
            if norm_row:
                normalised_rows.append(norm_row)

        subs = []
        for s in (raw.get("substitutes") or []):
            if isinstance(s, dict):
                subs.append({
                    "name": s.get("name") or s.get("fullName", ""),
                    "number": s.get("number") or s.get("shirtNumber"),
                    "position": s.get("position", "")
                })

        return {
            "name": team_name,
            "formation": raw.get("formation") or "",
            "initialLineup": normalised_rows,
            "substitutes": subs
        }

    home = _normalise_team(lineup_data.get("homeTeam"), home_team)
    away = _normalise_team(lineup_data.get("awayTeam"), away_team)

    if not home and not away:
        return None

    return {"home": home, "away": away}


# ── Box score ──────────────────────────────────────────────────────

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
            is_captain = p.get("isCaptain", False)
            offsides = p.get("offsides", 0)

            stats_list = _as_list(p.get("statistics"))
            stats = stats_list[0] if stats_list else {}

            goals = stats.get("goalsScored", 0)
            assists = stats.get("assists", 0)
            goals_saved = stats.get("goalsSaved", 0)
            goals_conceded = stats.get("goalsConceded", 0)

            xg = stats.get("expectedGoals", 0)
            xa = stats.get("expectedAssists", 0)
            xgot = stats.get("expectedGoalsOnTarget", 0)
            xgot_conceded = stats.get("expectedGoalsOnTargetConceded", 0)
            xgp = stats.get("expectedGoalsPrevented", 0)

            shots = stats.get("shotsTotal", 0)
            shots_ot = stats.get("shotsOnTarget", 0)
            shots_acc = stats.get("shotsAccuracy", "")

            dribbles_total = stats.get("dribblesTotal", 0)
            dribbles_succ = stats.get("dribblesSuccessful", 0)

            key_passes = stats.get("passesKey", 0)
            pass_acc = stats.get("passesAccuracy", "")
            passes_total = stats.get("passesTotal", 0)

            tackles = stats.get("tacklesTotal", 0)
            intercepts = stats.get("interceptionsTotal", 0)

            duels_total = stats.get("duelsTotal", 0)
            duels_won = stats.get("duelsWon", 0)
            duel_rate = stats.get("duelSuccessRate", "")

            fouled_by_others = stats.get("fouledByOthers", 0)
            fouled_others = stats.get("fouledOthers", 0)

            pens_scored = stats.get("penaltiesScored", 0)
            pens_missed = stats.get("penaltiesMissed", 0)

            cards_yellow = stats.get("cardsYellow", 0)
            cards_red = stats.get("cardsRed", 0)
            cards_second_yellow = stats.get("cardsSecondYellow", 0)

            try:
                rating_val = float(rating) if rating and rating != "N/A" else 0
            except (TypeError, ValueError):
                rating_val = 0

            is_notable = (
                rating_val >= 7.0
                or goals > 0
                or assists > 0
                or xg >= 0.3
                or goals_saved >= 3
                or cards_red > 0
                or cards_second_yellow > 0
            )
            if not is_notable:
                continue

            sub_str = " (sub)" if is_sub else ""
            captain_str = " (C)" if is_captain else ""
            line = f"  {name}{captain_str} [{position}{sub_str}, {mins}', Rating: {rating}]"

            stats_parts = []
            if goals: stats_parts.append(f"{goals} goal(s)")
            if assists: stats_parts.append(f"{assists} assist(s)")
            if pens_scored: stats_parts.append(f"{pens_scored} penalty/penalties scored")
            if pens_missed: stats_parts.append(f"{pens_missed} penalty/penalties missed")
            if xg: stats_parts.append(f"xG: {xg:.2f}")
            if xa: stats_parts.append(f"xA: {xa:.2f}")
            if xgot: stats_parts.append(f"xGOT: {xgot:.2f}")
            if shots: stats_parts.append(f"shots: {shots_ot}/{shots} on target ({shots_acc})" if shots_acc else f"shots: {shots_ot}/{shots} on target")
            if dribbles_total: stats_parts.append(f"dribbles: {dribbles_succ}/{dribbles_total} successful")
            if key_passes: stats_parts.append(f"key passes: {key_passes}")
            if pass_acc and passes_total: stats_parts.append(f"passing: {pass_acc} acc ({passes_total} attempted)")
            if duels_total: stats_parts.append(f"duels: {duels_won}/{duels_total} won ({duel_rate})" if duel_rate else f"duels: {duels_won}/{duels_total} won")
            if tackles or intercepts: stats_parts.append(f"tackles/intercepts: {tackles}/{intercepts}")
            if fouled_by_others: stats_parts.append(f"fouled: {fouled_by_others}")
            if fouled_others: stats_parts.append(f"fouls committed: {fouled_others}")
            if offsides: stats_parts.append(f"offsides: {offsides}")

            if position and "goalkeeper" in position.lower():
                if goals_saved: stats_parts.append(f"saves: {goals_saved}")
                if goals_conceded: stats_parts.append(f"goals conceded: {goals_conceded}")
                if xgot_conceded: stats_parts.append(f"xGOT conceded: {xgot_conceded:.2f}")
                if xgp: stats_parts.append(f"goals prevented (xGP): {xgp:.2f}")

            if cards_yellow: stats_parts.append(f"yellow card{'s' if cards_yellow > 1 else ''}: {cards_yellow}")
            if cards_second_yellow: stats_parts.append("second yellow (sent off)")
            if cards_red: stats_parts.append("red card")

            if stats_parts:
                line += " — " + ", ".join(stats_parts)
            lines.append(line)

    return "\n".join(lines) if len(lines) > 1 else None

def build_tournament_cache():
    session = Session()
    finished = session.query(Match).filter(
        Match.status.in_(["FINISHED", "Finished"])
    ).all()
    session.close()

    if not finished:
        return

    new_matches = [
        m for m in finished
        if m.match_id not in _tournament_stats_cache["matches_processed"]
    ]

    if not new_matches:
        return

    processed = 0

    for match in new_matches:
        highlightly_id = find_highlightly_match_id(
            match.home_team, match.away_team, match.match_date
        )

        box_score_data = _cache["box_scores"].get(highlightly_id) if highlightly_id else None
        match_detail = _cache["match_details"].get(highlightly_id) if highlightly_id else None

        _tournament_stats_cache["matches_processed"].add(match.match_id)

        if not box_score_data and not match_detail:
            continue

        if box_score_data:
            for team_data in box_score_data:
                t_name = (team_data.get("team") or {}).get("name", "")
                for p in _as_list(team_data.get("players", [])):
                    mins = p.get("minutesPlayed") or 0
                    if mins == 0:
                        continue
                    name = p.get("name") or p.get("fullName", "")
                    if not name:
                        continue

                    stats_list = _as_list(p.get("statistics"))
                    stats = stats_list[0] if stats_list else {}

                    if name not in _tournament_stats_cache["players"]:
                        _tournament_stats_cache["players"][name] = {
                            "team": t_name, "matches": 0, "minutes": 0,
                            "goals": 0, "assists": 0, "ratings": [],
                            "xg": 0.0, "xa": 0.0, "xgot": 0.0, "xgp": 0.0,
                            "shots_total": 0, "shots_on_target": 0,
                            "dribbles_successful": 0, "dribbles_total": 0,
                            "key_passes": 0, "passes_total": 0, "passes_successful": 0,
                            "duels_won": 0, "duels_total": 0,
                            "tackles": 0, "interceptions": 0,
                            "goals_saved": 0, "goals_conceded": 0,
                            "cards_yellow": 0, "cards_red": 0,
                            "fouls_committed": 0, "fouls_suffered": 0,
                        }

                    pc = _tournament_stats_cache["players"][name]
                    pc["matches"] += 1
                    pc["minutes"] += mins
                    pc["goals"] += stats.get("goalsScored", 0)
                    pc["assists"] += stats.get("assists", 0)
                    pc["shots_total"] += stats.get("shotsTotal", 0)
                    pc["shots_on_target"] += stats.get("shotsOnTarget", 0)
                    pc["dribbles_successful"] += stats.get("dribblesSuccessful", 0)
                    pc["dribbles_total"] += stats.get("dribblesTotal", 0)
                    pc["key_passes"] += stats.get("passesKey", 0)
                    pc["passes_total"] += stats.get("passesTotal", 0)
                    pc["passes_successful"] += stats.get("passesSuccessful", 0)
                    pc["duels_won"] += stats.get("duelsWon", 0)
                    pc["duels_total"] += stats.get("duelsTotal", 0)
                    pc["tackles"] += stats.get("tacklesTotal", 0)
                    pc["interceptions"] += stats.get("interceptionsTotal", 0)
                    pc["goals_saved"] += stats.get("goalsSaved", 0)
                    pc["goals_conceded"] += stats.get("goalsConceded", 0)
                    pc["cards_yellow"] += stats.get("cardsYellow", 0)
                    pc["cards_red"] += stats.get("cardsRed", 0)
                    pc["fouls_committed"] += stats.get("fouledOthers", 0)
                    pc["fouls_suffered"] += stats.get("fouledByOthers", 0)
                    pc["xg"] += _safe_float(stats.get("expectedGoals", 0)) or 0
                    pc["xa"] += _safe_float(stats.get("expectedAssists", 0)) or 0
                    pc["xgot"] += _safe_float(stats.get("expectedGoalsOnTarget", 0)) or 0
                    pc["xgp"] += _safe_float(stats.get("expectedGoalsPrevented", 0)) or 0
                    try:
                        r = float(p.get("matchRating") or 0)
                        if r > 0:
                            pc["ratings"].append(r)
                    except (TypeError, ValueError):
                        pass

        for team_name in (match.home_team, match.away_team):
            if team_name not in _tournament_stats_cache["teams"]:
                _tournament_stats_cache["teams"][team_name] = {
                    "matches": 0, "won": 0, "drawn": 0, "lost": 0,
                    "goals_for": 0, "goals_against": 0,
                    "xg_for": 0.0, "possession_total": 0.0, "possession_matches": 0,
                    "shots_on_target": 0, "corners": 0, "clean_sheets": 0,
                    "cards_yellow": 0, "cards_red": 0,
                }

        hc = _tournament_stats_cache["teams"][match.home_team]
        ac = _tournament_stats_cache["teams"][match.away_team]
        hg = match.home_score or 0
        ag = match.away_score or 0

        hc["matches"] += 1; ac["matches"] += 1
        hc["goals_for"] += hg; hc["goals_against"] += ag
        ac["goals_for"] += ag; ac["goals_against"] += hg
        if hg == 0: ac["clean_sheets"] += 1
        if ag == 0: hc["clean_sheets"] += 1
        if hg > ag: hc["won"] += 1; ac["lost"] += 1
        elif ag > hg: ac["won"] += 1; hc["lost"] += 1
        else: hc["drawn"] += 1; ac["drawn"] += 1

        if match_detail:
            for team_stats in _as_list(match_detail.get("statistics", [])):
                t_name = (team_stats.get("team") or {}).get("name", "")
                canonical = None
                if _names_match(t_name, match.home_team): canonical = match.home_team
                elif _names_match(t_name, match.away_team): canonical = match.away_team
                if not canonical:
                    continue
                tc = _tournament_stats_cache["teams"][canonical]
                values = {}
                for row in _as_list(team_stats.get("statistics", [])):
                    k = _first_present(row.get("displayName"), row.get("name"))
                    v = _first_present(row.get("value"), row.get("displayValue"))
                    if k and v is not None:
                        values[k] = v
                poss = values.get("Possession")
                if poss is not None:
                    try:
                        p_float = float(poss) if isinstance(poss, (int, float)) else float(str(poss).replace('%','').strip()) / 100
                        tc["possession_total"] += p_float
                        tc["possession_matches"] += 1
                    except (ValueError, TypeError):
                        pass
                xg = _safe_float(values.get("Expected Goals"))
                if xg: tc["xg_for"] += xg
                for stat_key, cache_key in [
                    ("Shots on target", "shots_on_target"),
                    ("Corners", "corners")
                ]:
                    val = values.get(stat_key)
                    if val:
                        try: tc[cache_key] += int(val)
                        except (ValueError, TypeError): pass

            for card in _extract_card_events(match_detail, (match.home_team, match.away_team)):
                tc = _tournament_stats_cache["teams"].get(card["team"])
                if not tc: continue
                if card["kind"] == "Yellow Card": tc["cards_yellow"] += 1
                elif card["kind"] == "Red Card": tc["cards_red"] += 1

        processed += 1

    if processed:
        print(f"Tournament cache updated — "
              f"{len(_tournament_stats_cache['players'])} players, "
              f"{len(_tournament_stats_cache['teams'])} teams tracked.")


def get_player_tournament_stats(player_name):
    build_tournament_cache()
    matched = _match_player_name(player_name, _tournament_stats_cache["players"].keys())
    if not matched:
        return None, player_name
    return _tournament_stats_cache["players"][matched], matched


def _match_player_name(name, candidates):
    if not name:
        return None
    if name in candidates:
        return name
    lowered = name.strip().lower()
    for candidate in candidates:
        if candidate.lower() == lowered:
            return candidate
    for candidate in candidates:
        if lowered in candidate.lower() or candidate.lower() in lowered:
            return candidate
    return None


def get_team_tournament_stats(team_name):
    build_tournament_cache()
    if team_name in _tournament_stats_cache["teams"]:
        return _tournament_stats_cache["teams"][team_name]
    canonical = TEAM_NAME_ALIASES.get(team_name, team_name)
    return _tournament_stats_cache["teams"].get(canonical)


def format_player_debate_context(player_names):
    build_tournament_cache()
    blocks = []
    not_found = []

    for name in player_names:
        stats, matched = get_player_tournament_stats(name)
        if not stats:
            not_found.append(name)
            continue

        avg_rating = sum(stats["ratings"]) / len(stats["ratings"]) if stats["ratings"] else None
        pass_acc = f"{round(stats['passes_successful'] / stats['passes_total'] * 100)}%" if stats["passes_total"] else None

        lines = [f"Player: {matched} ({stats['team']})"]
        lines.append(f"  Matches: {stats['matches']} ({stats['minutes']} mins)")
        lines.append(f"  Goals: {stats['goals']} | Assists: {stats['assists']}")
        lines.append(f"  xG: {stats['xg']:.2f} | xA: {stats['xa']:.2f}")
        if avg_rating:
            lines.append(f"  Avg match rating: {avg_rating:.2f} across {len(stats['ratings'])} match(es)")
        lines.append(f"  Shots: {stats['shots_on_target']}/{stats['shots_total']} on target")
        if stats["dribbles_total"]:
            lines.append(f"  Dribbles: {stats['dribbles_successful']}/{stats['dribbles_total']} successful")
        lines.append(f"  Key passes: {stats['key_passes']}")
        if pass_acc:
            lines.append(f"  Pass accuracy: {pass_acc} ({stats['passes_total']} attempted)")
        if stats["duels_total"]:
            lines.append(f"  Duels: {stats['duels_won']}/{stats['duels_total']} won")
        lines.append(f"  Tackles: {stats['tackles']} | Interceptions: {stats['interceptions']}")
        if stats["goals_saved"]:
            lines.append(f"  Goals saved: {stats['goals_saved']} | xGP: {stats['xgp']:.2f}")
        if stats["cards_yellow"] or stats["cards_red"]:
            lines.append(f"  Cards: {stats['cards_yellow']} yellow, {stats['cards_red']} red")
        blocks.append("\n".join(lines))

    result = "\n\n".join(blocks)
    if not_found:
        result += f"\n\nNote: No tournament data found for: {', '.join(not_found)}. They may not have appeared in any match yet, or the name doesn't match exactly."
    return result if blocks else None


def format_team_debate_context(team_names):
    build_tournament_cache()
    blocks = []
    not_found = []

    for name in team_names:
        stats = get_team_tournament_stats(name)
        if not stats:
            not_found.append(name)
            continue
        gd = stats["goals_for"] - stats["goals_against"]
        avg_poss = f"{round(stats['possession_total'] / stats['possession_matches'] * 100)}%" if stats["possession_matches"] else None

        lines = [f"Team: {name}"]
        lines.append(f"  Record: {stats['matches']}MP — {stats['won']}W {stats['drawn']}D {stats['lost']}L")
        lines.append(f"  Goals: {stats['goals_for']} scored, {stats['goals_against']} conceded (GD: {gd:+d})")
        lines.append(f"  Clean sheets: {stats['clean_sheets']}")
        lines.append(f"  xG for: {stats['xg_for']:.2f}")
        if avg_poss:
            lines.append(f"  Avg possession: {avg_poss}")
        if stats["shots_on_target"]:
            lines.append(f"  Shots on target: {stats['shots_on_target']}")
        if stats["corners"]:
            lines.append(f"  Corners won: {stats['corners']}")
        if stats["cards_yellow"] or stats["cards_red"]:
            lines.append(f"  Cards: {stats['cards_yellow']} yellow, {stats['cards_red']} red")
        blocks.append("\n".join(lines))

    result = "\n\n".join(blocks)
    if not_found:
        result += f"\n\nNote: No tournament data found for: {', '.join(not_found)}."
    return result if blocks else None

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
    data = _hl_get("players", {"name": player_name, "limit": 5})
    players = _as_list(data)

    if not players:
        return None

    player = players[0]
    player_id = player.get("id")
    if not player_id:
        return None

    summary_data = _hl_get(f"players/{player_id}")
    summary = _as_list(summary_data)
    summary = summary[0] if summary else {}

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