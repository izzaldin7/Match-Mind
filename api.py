from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import Session, Match
from ai import generate_match_briefing
from scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app):
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

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

@app.get("/matches/{match_id}/briefing")
def get_match_briefing(match_id: int):
    session = Session()
    match = session.query(Match).filter_by(match_id=match_id).first()
    session.close()

    if not match:
        return {"error": "Match not found"}
    
    briefing = generate_match_briefing(
        home_team = match.home_team,
        away_team = match.away_team,
        match_date = match.match_date,
        stage = match.stage,
        group = match.group_name
    )

    return {
        "match_id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "date": match.match_date,
        "stage": match.stage,
        "group": match.group_name,
        "briefing": briefing
    }

@app.get("/matches/{match_id}/report")
def get_post_match_report(match_id: int):
    session = Session()
    match = session.query(Match).filter_by(match_id=match_id).first()
    session.close()

    if not match:
        return {"error": "Match not found"}
    if match.status != "FINISHED":
        return {"error": f"Match is not finished yet. Current status: {match.status}"}
    
    report = get_post_match_report(
        home_team = match.home_team,
        away_team = match.away_team,
        home_score = match.home_score,
        away_score = match.away_score,
        stage = match.stage,
        group = match.group_name
    )

    return {
        "match_id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "stage": match.stage,
        "group": match.group_name,
        "report": report
    }