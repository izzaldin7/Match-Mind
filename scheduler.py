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
    response = requests.get(url, headers=headers)
    data = response.json()

    session = Session()
    for match in data['matches']:
        existing = session.query(Match).filter_by(match_id=match['id']).first()
        if existing:
            existing.status = match['status']
            existing.home_score = match['score']['fullTime']['home']
            existing.away_score = match['score']['fullTime']['away']
        else:
            new_match = Match(
                match_id = match['id'],
                home_team = match['homeTeam']['name'],
                away_team = match['awayTeam']['name'],
                match_date = match['utcDate'][:10],
                status = match['status'],
                home_score = match['score']['fullTime']['home'],
                away_score = match['score']['fullTime']['away'],
                stage = match['stage'],
                group_name = match.get('group')
            )
            session.add(new_match)

    session.commit()
    session.close()
    print("Match data refreshed successfully.")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_match_data, 'interval', minutes=5)
    scheduler.start()
    print("Scheduler started - refreshing every 5 minutes.")
    return scheduler
