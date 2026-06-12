import requests
from bs4 import BeautifulSoup
from database import Session, Match
from dotenv import load_dotenv
import os

load_dotenv()

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
FOOTBALL_HEADERS = {"X-Auth-Token": FOOTBALL_API_KEY}
WIKI_HEADERS = {"User-Agent": "MatchMind/1.0 (portfolio project)"}


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
                    "gf": 0,
                    "ga": 0,
                    "gd": 0,
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

# ---- football-data.org match events ---------------------

def fetch_match_events(match_id):
    """
    Fetches real match data from football-data.org individual match endpoint.
    Returns goals, cards, lineups and stats as a formatted string for AI prompts.
    """
    try:
        url = f"https://api.football-data.org/v4/matches/{match_id}"
        response = requests.get(url, headers = FOOTBALL_HEADERS, timeout=10)

        if response.status_code != 200:
            print(f"Match events fetch failed: {response.status_code}")
            return None
        
        data = response.json()
        lines = []

        #Goals
        goals = data.get("goals", [])
        if goals:
            lines.append("Goals:")
            for g in goals:
                scorer = g.get("scorer", {}).get("name", "Unknown")
                team = g.get("team", {}).get("name", "Unknown")
                minute = g.get("minute", "?")
                own_goal = " (OG)" if g.get("type") == "OWN" else ""
                penalty = " (Pen)" if g.get("type") == "PENALTY" else ""
                lines.append(f" {minute}' {scorer}{own_goal}{penalty} ({team})")

        #Cards
        bookings = data.get("bookings", [])
        if bookings:
            lines.append("\nCards:")
            for b in bookings:
                player = b.get("player", {}).get("name", "Unknown")
                team = b.get("team", {}).get("name", "Unknown")
                minute = b.get("minute", "?")
                card = b.get("card", "YELLOW_CARD")
                card_str = "Red Card" if "RED" in card else "Yellow Card"
                lines.append(f" {minute}' {card_str} - {player} ({team})")

        return "\n".join(lines) if lines else None
    
    except Exception as e:
        print(f"Match events fetch error: {e}")
        return None
    
# ---- Wikipedia group context for briefings ----------------------

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

        