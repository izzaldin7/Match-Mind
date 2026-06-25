from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, Match
import requests
from dotenv import load_dotenv
import os
from utils import build_tournament_cache

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")
url = "https://api.football-data.org/v4/competitions/WC/matches"
headers = {"X-Auth-Token": API_KEY}


def score_value(match, side):
    score = match.get("score") or {}
    for key in ("fullTime", "regularTime", "current", "halfTime"):
        score_block = score.get(key)
        if isinstance(score_block, dict) and score_block.get(side) is not None:
            return score_block.get(side)
    return None


def should_keep_existing_live_state(existing, incoming_status, incoming_home_score, incoming_away_score):
    existing_status = (existing.status or "").upper()
    incoming_status = (incoming_status or "").upper()
    incoming_has_no_score = incoming_home_score is None and incoming_away_score is None
    return (
        existing_status in ("LIVE", "IN_PLAY", "PAUSED", "HALFTIME")
        and incoming_status in ("TIMED", "SCHEDULED")
        and incoming_has_no_score
    )


def refresh_match_data():
    print("Refreshing match data from football-data.org....")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch match data: {e}")
        print("Skipping this refresh cycle, will retry in 5 minutes.")
        return

    print(f"API returned {len(data['matches'])} matches")

    session = Session()
    try:
        for match in data['matches']:
            existing = session.query(Match).filter_by(match_id=match['id']).first()
            incoming_status = match['status']
            incoming_home_score = score_value(match, "home")
            incoming_away_score = score_value(match, "away")
            if existing:
                print(f"Updating {match['homeTeam']['name']} vs {match['awayTeam']['name']}: {incoming_status}")
                if should_keep_existing_live_state(existing, incoming_status, incoming_home_score, incoming_away_score):
                    print("Keeping existing live state; upstream returned scheduled/null data for an active match.")
                else:
                    existing.status = incoming_status
                    existing.home_score = incoming_home_score
                    existing.away_score = incoming_away_score
                existing.kick_off_time = match['utcDate'][11:16] + " UTC"
            else:
                new_match = Match(
                    match_id=match['id'],
                    home_team=match['homeTeam']['name'],
                    away_team=match['awayTeam']['name'],
                    match_date=match['utcDate'][:10],
                    status=incoming_status,
                    home_score=incoming_home_score,
                    away_score=incoming_away_score,
                    stage=match['stage'],
                    group_name=match.get('group'),
                    kick_off_time=match['utcDate'][11:16] + " UTC"
                )
                session.add(new_match)

        session.commit()
        print("Match data refreshed successfully.")
        try:
            build_tournament_cache()
        except Exception as cache_error:
            print(f"Match data saved, but tournament cache update failed: {cache_error}")
    except Exception as e:
        print(f"Error updating database: {e}")
        session.rollback()
    finally:
        session.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_match_data, 'interval', minutes=30)
    scheduler.start()
    try:
        refresh_match_data()
    except Exception as e:
        print(f"Initial refresh failed, will retry on next scheduled interval: {e}")
    print("Scheduler started - refreshing every 30 minutes.")
    return scheduler
