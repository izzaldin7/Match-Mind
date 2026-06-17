import requests
from bs4 import BeautifulSoup
from database import Session, Match
from dotenv import load_dotenv
import os

load_dotenv()

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALL_HEADERS = {"X-Auth-Token": FOOTBALL_API_KEY}
WIKI_HEADERS = {"User-Agent": "MatchMind/1.0 (portfolio project)"}


# ── Standings from DB ──────────────────────────────────────────────

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
                    "team": team,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "gf": 0,
                    "ga": 0,
                    "gd": 0,
                    "points": 0
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

    sorted_standings = sorted(
        standings.values(),
        key=lambda x: (x["points"], x["gd"], x["gf"]),
        reverse=True
    )
    return sorted_standings


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


# ── football-data.org match details + scorers ──────────────────────

def fetch_match_details(match_id):
    """
    Fetches half-time score and referee from football-data.org.
    Confirmed available on free tier.
    """
    try:
        url = f"https://api.football-data.org/v4/matches/{match_id}"
        response = requests.get(url, headers=FOOTBALL_HEADERS, timeout=10)

        if response.status_code != 200:
            print(f"Match details fetch failed: {response.status_code}")
            return None

        data = response.json()
        details = {}

        score = data.get("score", {})
        half_time = score.get("halfTime", {})
        if half_time.get("home") is not None:
            details["half_time"] = f"{half_time.get('home')}-{half_time.get('away')}"

        referees = data.get("referees", [])
        if referees:
            details["referee"] = referees[0].get("name")
            details["referee_nationality"] = referees[0].get("nationality")

        return details if details else None

    except Exception as e:
        print(f"Match details fetch error: {e}")
        return None


def fetch_team_scorers(team_name):
    """
    Fetches the tournament's scorers list and filters for the given team.
    Returns each player's goal/assist tally for the tournament so far.
    Confirmed available on free tier.
    """
    try:
        url = "https://api.football-data.org/v4/competitions/WC/scorers"
        params = {"limit": 100}
        response = requests.get(url, headers=FOOTBALL_HEADERS, params=params, timeout=10)

        if response.status_code != 200:
            print(f"Scorers fetch failed: {response.status_code}")
            return None

        data = response.json()
        scorers = data.get("scorers", [])

        team_scorers = []
        for s in scorers:
            if s.get("team", {}).get("name") == team_name:
                team_scorers.append({
                    "name": s["player"]["name"],
                    "goals": s["goals"],
                    "assists": s.get("assists"),
                    "played_matches": s["playedMatches"]
                })

        return team_scorers if team_scorers else None

    except Exception as e:
        print(f"Team scorers fetch error: {e}")
        return None


def format_team_scorers(team_name):
    """
    Returns a formatted string of a team's goal involvements so far in the
    tournament, for use in pre-match briefings.
    """
    scorers = fetch_team_scorers(team_name)
    if not scorers:
        return None

    lines = [f"{team_name} - goal involvements so far this tournament:"]
    for s in scorers:
        assist_str = f", {s['assists']} assist(s)" if s['assists'] else ""
        match_word = "match" if s['played_matches'] == 1 else "matches"
        lines.append(f"  {s['name']}: {s['goals']} goal(s) in {s['played_matches']} {match_word}{assist_str}")

    return "\n".join(lines)


def get_match_context(match_id, home_team, away_team):
    """
    Builds a combined real-data context string for post-match reports:
    half-time score, referee, and goal involvements for both teams
    from the tournament's official scorer list.
    """
    lines = []

    details = fetch_match_details(match_id)
    if details:
        if "half_time" in details:
            lines.append(f"Half-time score: {details['half_time']}")
        if "referee" in details:
            ref_nat = f" ({details['referee_nationality']})" if details.get("referee_nationality") else ""
            lines.append(f"Referee: {details['referee']}{ref_nat}")

    home_scorers = fetch_team_scorers(home_team)
    if home_scorers:
        lines.append(f"\n{home_team} - goal involvements so far this tournament:")
        for s in home_scorers:
            assist_str = f", {s['assists']} assist(s)" if s['assists'] else ""
            match_word = "match" if s['played_matches'] == 1 else "matches"
            lines.append(f"  {s['name']}: {s['goals']} goal(s) in {s['played_matches']} {match_word}{assist_str}")

    away_scorers = fetch_team_scorers(away_team)
    if away_scorers:
        lines.append(f"\n{away_team} - goal involvements so far this tournament:")
        for s in away_scorers:
            assist_str = f", {s['assists']} assist(s)" if s['assists'] else ""
            match_word = "match" if s['played_matches'] == 1 else "matches"
            lines.append(f"  {s['name']}: {s['goals']} goal(s) in {s['played_matches']} {match_word}{assist_str}")

    return "\n".join(lines) if lines else None


# ── Wikipedia scraping ─────────────────────────────────────────────

def _group_letter(group_name):
    return group_name.replace("GROUP_", "").strip()


def scrape_group_context(group_name):
    """
    Scrapes Wikipedia's group page for historical h2h context.
    Used to enrich match briefings.
    """
    letter = _group_letter(group_name)
    url = f"https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_{letter}"

    try:
        response = requests.get(url, headers=WIKI_HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        content_div = soup.find("div", {"id": "mw-content-text"})
        if not content_div:
            return None

        paragraphs = content_div.find_all("p")
        text_blocks = []

        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 60:
                text_blocks.append(text)

        return "\n\n".join(text_blocks[:6]) if text_blocks else None

    except Exception as e:
        print(f"Wikipedia group scrape failed: {e}")
        return None


def scrape_motm(home_team, away_team):
    """
    Scrapes Wikipedia's individual match page for the Man of the Match award.
    Returns the MOTM name as a string, or None if not available yet.
    """
    home_wiki = home_team.replace(" ", "_")
    away_wiki = away_team.replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{home_wiki}_v_{away_wiki}_(2026_FIFA_World_Cup)"

    try:
        response = requests.get(url, headers=WIKI_HEADERS, timeout=10)

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        infobox = soup.find("table", {"class": "infobox"})
        if not infobox:
            return None

        rows = infobox.find_all("tr")
        for row in rows:
            header = row.find("th")
            data = row.find("td")
            if header and data:
                header_text = header.get_text(strip=True).lower()
                if "man of the match" in header_text or "motm" in header_text or "player of the match" in header_text:
                    return data.get_text(strip=True)

        return None

    except Exception as e:
        print(f"Wikipedia MOTM scrape failed: {e}")
        return None
    
def scrape_match_summary(home_team, away_team):
    """
    Scrapes the main 2026 FIFA World Cup Wikipedia page for the paragraph
    summarizing a specific match. This page is updated quickly after matches
    with goals, minutes, and disciplinary incidents.
    """
    url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"

    try:
        response = requests.get(url, headers=WIKI_HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        content_div = soup.find("div", {"id": "mw-content-text"})
        if not content_div:
            return None

        paragraphs = content_div.find_all("p")

        for p in paragraphs:
            text = p.get_text(strip=True)
            if home_team in text and away_team in text and len(text) > 100:
                return text

        return None

    except Exception as e:
        print(f"Wikipedia match summary scrape failed: {e}")
        return None