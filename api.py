from fastapi import FastAPI
from database import Session, Match

app = FastAPI()

@app.get("/")
def root():
    return {"message": "MatchMind API is running"}

@app.get("/matches")
def get_matches():
    session = Session()
    matches = session.query(Match).all()
    session.close()
    return [
        {
            "match_id": m.match_id,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "date": m.match_date,
            "status": m.status,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "stage": m.stage,
            "group": m.group_name
        }
        for m in matches
    ]

@app.get("/matches/today")
def get_today_matches():
    from datetime import date
    today = str(date.today())
    session = Session()
    matches = session.query(Match).filter_by(match_date=today).all()
    session.close()
    return [
        {
            "match_id": m.match_id,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "status": m.status,
            "home_score": m.home_score,
            "away_score": m.away_score
        }
        for m in matches
    ]