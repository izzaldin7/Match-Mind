from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager
from database import Session, Match
from ai import (
    build_match_briefing_context,
    build_post_match_context,
    generate_match_briefing,
    generate_post_match_report
)
from scheduler import start_scheduler

@asynccontextmanager
async def lifespan(app):
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)


def get_db():
    session = Session()
    try:
        yield session
    finally:
        session.close()

@app.get("/")
def root():
    return {"message": "MatchMind API is running"}

@app.get("/matches")
def get_matches(session=Depends(get_db)):
    matches = session.query(Match).all()
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
def get_today_matches(session=Depends(get_db)):
    from datetime import date
    today = str(date.today())
    matches = session.query(Match).filter_by(match_date=today).all()
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
def get_match_briefing(match_id: int, session=Depends(get_db)):
    from datetime import date
    match = session.query(Match).filter_by(match_id=match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status in ("FINISHED", "Finished"):
        raise HTTPException(status_code=400, detail="This match has already finished. Try the /report endpoint instead.")
    if match.match_date != str(date.today()):
        raise HTTPException(status_code=400, detail=f"Briefings are only available for today's matches. This match is scheduled for {match.match_date}.")

    try:
        data_used = build_match_briefing_context(
            home_team=match.home_team,
            away_team=match.away_team,
            match_date=match.match_date,
            stage=match.stage,
            group=match.group_name,
            match_id=match.match_id
        )
        briefing = generate_match_briefing(
            home_team=match.home_team,
            away_team=match.away_team,
            match_date=match.match_date,
            stage=match.stage,
            group=match.group_name,
            match_id=match.match_id,
            context=data_used
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "match_id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "date": match.match_date,
        "stage": match.stage,
        "group": match.group_name,
        "data_used": data_used,
        "briefing": briefing
    }

@app.get("/matches/{match_id}/report")
def get_post_match_report(match_id: int, session=Depends(get_db)):
    match = session.query(Match).filter_by(match_id=match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status not in ("FINISHED", "Finished"):
        raise HTTPException(
            status_code=400,
            detail=f"Match is not finished yet. Current status: {match.status}"
        )
    try:
        data_used = build_post_match_context(
            home_team=match.home_team,
            away_team=match.away_team,
            home_score=match.home_score,
            away_score=match.away_score,
            stage=match.stage,
            group=match.group_name,
            match_id=match.match_id,
            match_date=match.match_date
        )
        report = generate_post_match_report(
            home_team=match.home_team,
            away_team=match.away_team,
            home_score=match.home_score,
            away_score=match.away_score,
            stage=match.stage,
            group=match.group_name,
            match_id=match.match_id,
            match_date=match.match_date,
            context=data_used
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "match_id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "stage": match.stage,
        "group": match.group_name,
        "data_used": data_used,
        "report": report
    }