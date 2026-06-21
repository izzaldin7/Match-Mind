from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, Match
import requests
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")
url = "https://api.football-data.org/v4/competitions/WC/matches"
headers = {"X-Auth-Token": API_KEY}


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
            if existing:
                print(f"Updating {match['homeTeam']['name']} vs {match['awayTeam']['name']}: {match['status']}")
                existing.status = match['status']
                existing.home_score = match['score']['fullTime']['home']
                existing.away_score = match['score']['fullTime']['away']
                existing.kick_off_time = match['utcDate'][11:16] + " UTC"
            else:
                new_match = Match(
                    match_id=match['id'],
                    home_team=match['homeTeam']['name'],
                    away_team=match['awayTeam']['name'],
                    match_date=match['utcDate'][:10],
                    status=match['status'],
                    home_score=match['score']['fullTime']['home'],
                    away_score=match['score']['fullTime']['away'],
                    stage=match['stage'],
                    group_name=match.get('group'),
                    kick_off_time=match['utcDate'][11:16] + " UTC"
                )
                session.add(new_match)

        session.commit()
        print("Match data refreshed successfully.")
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