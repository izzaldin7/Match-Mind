from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
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
    build_player_debate_context,
    format_team_debate_context,
    build_tournament_cache,
    get_cached_content,
    get_group_standings,
    save_cached_content,
    BRIEFING_CACHE_TTL_SECONDS,
    find_highlightly_match_id,
    fetch_lineup,
    format_lineup_for_cache
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


def inferred_status(match):
    status = match.status or ""
    status_upper = status.upper()
    if status_upper not in ("TIMED", "SCHEDULED"):
        return status
    if not match.match_date or not match.kick_off_time:
        return status

    try:
        raw_time = match.kick_off_time.split()[0]
        kick_time = time.fromisoformat(raw_time)
        kickoff = datetime.combine(
            datetime.fromisoformat(match.match_date).date(),
            kick_time,
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return status

    now = datetime.now(timezone.utc)
    if kickoff <= now < kickoff + timedelta(hours=2, minutes=30):
        return "LIVE"
    return status


def serialize_match(match, include_date=True):
    payload = {
        "match_id": match.match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "status": inferred_status(match),
        "home_score": match.home_score,
        "away_score": match.away_score,
        "group": match.group_name,
        "kick_off_time": match.kick_off_time
    }
    if include_date:
        payload["date"] = match.match_date
        payload["stage"] = match.stage
    return payload


# ── Existing endpoints ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "MatchMind API is running"}

@app.get("/matches")
def get_matches(session=Depends(get_db)):
    matches = session.query(Match).all()
    return [serialize_match(m) for m in matches]

@app.get("/matches/today")
def get_today_matches(session=Depends(get_db)):
    today = str(datetime.now(timezone.utc).date())
    matches = session.query(Match).filter(Match.match_date.in_([today])).all()
    return [serialize_match(m, include_date=False) for m in matches]

@app.get("/standings/{group_name}")
def get_standings(group_name: str):
    normalized_group = group_name.strip().upper().replace(" ", "_")
    if len(normalized_group) == 1:
        normalized_group = f"GROUP_{normalized_group}"
    elif normalized_group.startswith("GROUP_") is False and normalized_group.startswith("GROUP"):
        normalized_group = normalized_group.replace("GROUP", "GROUP_", 1)

    return get_group_standings(normalized_group) or []

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


# ── Lineup endpoint ────────────────────────────────────────────────

@app.get("/matches/{match_id}/lineup")
def get_match_lineup(match_id: int, session=Depends(get_db)):
    """
    Returns lineup data for any match (upcoming, live, or finished).
    Available from ~30 min before kickoff per Highlightly docs.
    Cached permanently once retrieved — lineups never change after release.
    """
    match = session.query(Match).filter_by(match_id=match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Check permanent cache first (lineups never change once confirmed)
    cached = get_cached_content(match_id, "lineup")
    if cached:
        return cached

    # Resolve Highlightly match ID
    highlightly_id = find_highlightly_match_id(
        match.home_team, match.away_team, match.match_date
    )
    if not highlightly_id:
        raise HTTPException(
            status_code=404,
            detail="This match could not be matched to Highlightly data. Try again closer to kickoff."
        )

    # Fetch and normalise
    raw = fetch_lineup(highlightly_id)
    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Lineup not available yet. Lineups are released ~30 minutes before kickoff."
        )

    lineup = format_lineup_for_cache(raw, match.home_team, match.away_team)
    if not lineup:
        raise HTTPException(
            status_code=404,
            detail="Lineup data was returned but could not be parsed. Try again later."
        )

    result = {
        "match_id": match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "date": match.match_date,
        "status": match.status,
        "lineup": lineup
    }

    # Only cache permanently if the match is finished or lineup is clearly complete
    # (both teams have starters). For upcoming/live matches we still cache briefly
    # by using the same save_cached_content — a subsequent request within the same
    # server session hits the in-memory _cache["lineups"] anyway.
    home_rows = lineup.get("home", {}).get("initialLineup", [])
    away_rows = lineup.get("away", {}).get("initialLineup", [])
    is_complete = len(home_rows) >= 2 and len(away_rows) >= 2

    if match.status in ("FINISHED", "Finished") or is_complete:
        save_cached_content(match_id, "lineup", result)

    return result


# ── Debate endpoints ───────────────────────────────────────────────

class DebatePlayersRequest(BaseModel):
    players: List[str]

class DebateTeamsRequest(BaseModel):
    teams: List[str]

def _validate_player_positions(position_groups):
    """
    Rules:
    - Goalkeepers can only be compared with goalkeepers
    - Defenders can only be compared with defenders
    - Midfielders and attackers can be compared with each other
    Returns an error string or None if valid.
    """
    unique = set(position_groups)
    if "unknown" in unique:
        unique.discard("unknown")

    if "goalkeeper" in unique and len(unique) > 1:
        return "Goalkeepers can only be compared with other goalkeepers."
    if "defender" in unique and (unique - {"defender"}):
        return "Defenders can only be compared with other defenders."
    return None

@app.post("/debate/players")
def debate_players(request: DebatePlayersRequest):
    if len(request.players) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 players to compare.")
    if len(request.players) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 players can be compared at once.")
    debate_context = build_player_debate_context(request.players)
    if debate_context["missing"]:
        missing = ", ".join(debate_context["missing"])
        raise HTTPException(
            status_code=404,
            detail=(
                f"No tournament data found for: {missing}. "
                "Use the player's name as it appears in the cached World Cup match data, "
                "or wait until their team's finished-match box scores have been cached."
            )
        )
    position_error = _validate_player_positions(debate_context["position_groups"])
    if position_error:
        raise HTTPException(status_code=400, detail=position_error)
    context_str = debate_context["context"]
    if not context_str:
        raise HTTPException(status_code=404, detail="No tournament data found for the requested players. They may not have appeared in any match yet.")
    matched_players = debate_context["matched_players"]
    try:
        debate = generate_player_debate(
            matched_players, 
            context_str,
            debate_context["position_groups"])
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "type": "players",
        "subjects": matched_players,
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
