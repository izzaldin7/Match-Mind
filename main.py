import requests
from database import Session, Match
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("FOOTBALL_API_KEY")

url = "https://api.football-data.org/v4/competitions/WC/matches"
headers = {"X-Auth-Token": API_KEY}

response = requests.get(url, headers=headers)
data = response.json()

session = Session()

for match in data['matches']:
    existing = session.query(Match).filter_by(match_id=match['id']).first()
    if not existing:
        m = Match(
            match_id=match['id'],
            home_team=match['homeTeam']['name'],
            away_team=match['awayTeam']['name'],
            match_date=match['utcDate'][:10],
            status=match['status'],
            home_score=match['score']['fullTime']['home'],
            away_score=match['score']['fullTime']['away'],
            stage=match['stage'],
            group_name=match.get('group')
        )
        session.add(m)

session.commit()
session.close()
print("Fixtures saved to database!")


        