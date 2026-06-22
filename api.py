from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List
from database import Session, Match
from ai import (
    build_match_briefing_context,
    build_post_match_context,
    generate_match_briefing,
    generate_post_match_report,
    generate_player_debate,
    generate_team_debate
)
from utils import (
    format_player_debate_context,
    format_team_debate_context,
    build_tournament_cache,
    get_cached_content,
    save_cached_content,
    BRIEFING_CACHE_TTL_SECONDS
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


# ── Existing endpoints ─────────────────────────────────────────────

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
            "group": m.group_name,
            "kick_off_time": m.kick_off_time
        }
        for m in matches
    ]

@app.get("/matches/today")
def get_today_matches(session=Depends(get_db)):
    from datetime import datetime, timezone
    today = str(datetime.now(timezone.utc).date())
    matches = session.query(Match).filter(Match.match_date.in_([today])).all()
    return [
        {
            "match_id": m.match_id,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "status": m.status,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "group": m.group_name,
            "kick_off_time": m.kick_off_time
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

    # Briefings CAN go stale before kickoff (standings/qualification/discipline
    # can change), so this uses a TTL rather than caching forever.
    cached = get_cached_content(match_id, "briefing", ttl_seconds=BRIEFING_CACHE_TTL_SECONDS)
    if cached:
        return cached

    try:
        data_used = build_match_briefing_context(
            home_team=match.home_team, away_team=match.away_team,
            match_date=match.match_date, stage=match.stage,
            group=match.group_name, match_id=match.match_id
        )
        briefing = generate_match_briefing(
            home_team=match.home_team, away_team=match.away_team,
            match_date=match.match_date, stage=match.stage,
            group=match.group_name, match_id=match.match_id,
            context=data_used
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result = {
        "match_id": match_id,
        "home_team": match.home_team, "away_team": match.away_team,
        "date": match.match_date, "stage": match.stage,
        "group": match.group_name, "data_used": data_used, "briefing": briefing
    }
    save_cached_content(match_id, "briefing", result)
    return result

@app.get("/matches/{match_id}/report")
def get_post_match_report(match_id: int, session=Depends(get_db)):
    match = session.query(Match).filter_by(match_id=match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status not in ("FINISHED", "Finished"):
        raise HTTPException(status_code=400, detail=f"Match is not finished yet. Current status: {match.status}")

    # Reports are cached forever (no ttl) — a finished match's facts don't
    # change, so there's never a reason to regenerate one.
    cached = get_cached_content(match_id, "report")
    if cached:
        return cached

    try:
        data_used = build_post_match_context(
            home_team=match.home_team, away_team=match.away_team,
            home_score=match.home_score, away_score=match.away_score,
            stage=match.stage, group=match.group_name,
            match_id=match.match_id, match_date=match.match_date
        )
        report = generate_post_match_report(
            home_team=match.home_team, away_team=match.away_team,
            home_score=match.home_score, away_score=match.away_score,
            stage=match.stage, group=match.group_name,
            match_id=match.match_id, match_date=match.match_date,
            context=data_used
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result = {
        "match_id": match_id,
        "home_team": match.home_team, "away_team": match.away_team,
        "home_score": match.home_score, "away_score": match.away_score,
        "stage": match.stage, "group": match.group_name,
        "data_used": data_used, "report": report
    }
    save_cached_content(match_id, "report", result)
    return result


# ── Debate endpoints ───────────────────────────────────────────────

class DebatePlayersRequest(BaseModel):
    players: List[str]

class DebateTeamsRequest(BaseModel):
    teams: List[str]

@app.post("/debate/players")
def debate_players(request: DebatePlayersRequest):
    if len(request.players) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 players to compare.")
    if len(request.players) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 players can be compared at once.")
    context_str = format_player_debate_context(request.players)
    if not context_str:
        raise HTTPException(status_code=404, detail="No tournament data found for the requested players. They may not have appeared in any match yet.")
    try:
        debate = generate_player_debate(request.players, context_str)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "type": "players",
        "subjects": request.players,
        "context": context_str,
        "debate": debate
    }

@app.post("/debate/teams")
def debate_teams(request: DebateTeamsRequest):
    if len(request.teams) != 2:
        raise HTTPException(status_code=400, detail="Team debate requires exactly 2 teams.")
    context_str = format_team_debate_context(request.teams)
    if not context_str:
        raise HTTPException(status_code=404, detail="No tournament data found for the requested teams.")
    try:
        debate = generate_team_debate(request.teams, context_str)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "type": "teams",
        "subjects": request.teams,
        "context": context_str,
        "debate": debate
    }