from groq import Groq
from dotenv import load_dotenv
import os
from utils import (
    format_standings_for_prompt,
    get_match_context,
    get_head_to_head,
    get_team_tournament_form
)

load_dotenv()

client = None


def get_groq_client():
    global client
    if client:
        return client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment.")

    client = Groq(api_key=api_key)
    return client


def build_match_briefing_context(home_team, away_team, match_date, stage, group=None, match_id=None):
    group_info = group.replace("GROUP_", "Group ") if group else stage
    context = {
        "fixture": f"{home_team} vs {away_team}",
        "date": match_date,
        "stage": group_info,
        "standings": None,
        "goal_involvements": None,
        "head_to_head": None
    }

    if group:
        context["standings"] = format_standings_for_prompt(group, exclude_match_id=match_id)

    home_form = get_team_tournament_form(home_team, exclude_match_id=match_id)
    away_form = get_team_tournament_form(away_team, exclude_match_id=match_id)
    scorer_blocks = [block for block in (home_form, away_form) if block]
    if scorer_blocks:
        context["goal_involvements"] = "\n\n".join(scorer_blocks)

    context["head_to_head"] = get_head_to_head(home_team, away_team)
    return context


def build_post_match_context(home_team, away_team, home_score, away_score, stage, group=None, match_id=None, match_date=None):
    group_info = group.replace("GROUP_", "Group ") if group else stage

    if home_score is None or away_score is None:
        outcome = "the final score is unavailable"
    elif home_score > away_score:
        outcome = f"{home_team} won"
    elif away_score > home_score:
        outcome = f"{away_team} won"
    else:
        outcome = "the match ended in a draw"

    result = f"{home_team} {home_score}-{away_score} {away_team}"

    context = {
        "result": result,
        "stage": group_info,
        "outcome": outcome,
        "standings": None,
        "match_data": None
    }

    if group:
        context["standings"] = format_standings_for_prompt(group)

    if match_date:
        context["match_data"] = get_match_context(
            home_team,
            away_team,
            match_date=match_date,
            highlightly_match_id=None
        )

    return context


def _context_block(title, value):
    if value:
        return f"{title}:\n{value}"
    return f"{title}: Not available."


def generate_match_briefing(home_team, away_team, match_date, stage, group=None, match_id=None, context=None):
    if context is None:
        context = build_match_briefing_context(
            home_team,
            away_team,
            match_date,
            stage,
            group=group,
            match_id=match_id
        )

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a pre-match briefing for the following fixture:

    Fixture: {context["fixture"]}
    Date: {context["date"]}
    Stage: {context["stage"]}

    AVAILABLE DATA

    {_context_block("Current standings", context["standings"])}

    {_context_block("Tournament goal involvements", context["goal_involvements"])}

    {_context_block("Head-to-head history", context["head_to_head"])}

    This is the World Cup — write with a sense of occasion and genuine weight.
    Be engaging and vivid where the moment calls for it, but always grounded and
    intelligent. Every sentence should earn its place. No hollow hype or clichés.

    Structure your briefing as follows:
    - An opening line that captures the mood and stakes of this fixture
    - What the current standings mean for both teams — the pressure, the opportunity,
      what a win, draw or loss does to their tournament hopes. Be specific to their
      actual situation in the table, not generic.
    - If players are listed above with goal involvements this tournament, weave
      them in naturally — e.g. a player who has already scored may be looking to
      add to his tally, or a team's goal threat may be concentrated in one player.
      Only reference players listed above.
    - Any relevant historical context between these teams from the head-to-head
      data, if present.
    - A brief tactical outlook — how each side might approach this game given
      what's at stake
    - A considered prediction with a clear reason behind it

    ABSOLUTE RULES — these cannot be broken under any circumstances:
    - Your briefing must be driven by the AVAILABLE DATA above. If standings,
      goal involvements, or head-to-head history are available, use them directly
      and specifically in the briefing.
    - If a category says "Not available", do not invent it and do not write as if
      you know it. Briefly say that reliable data is not available where relevant.
    - Only mention player names that explicitly appear in the data provided above
      (goal involvements section or head-to-head context). Do not recall, assume,
      or invent any player names from your training data.
    - Do not mention, imply, or reference any disciplinary incidents — cards, red
      cards, suspensions, or bans — for either team under any circumstances, unless
      such information explicitly and literally appears in the data provided above.
    - Measure each team's situation purely from the standings and data provided.
      Do not assume form, tactics, or results beyond what the data shows.
    - If the standings show no matches played yet, do not invent any prior context.
    - No exclamation marks. Confident, assured tone throughout.
    - Keep it under 220 words.
    """

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def generate_post_match_report(home_team, away_team, home_score, away_score, stage, group=None, match_id=None, match_date=None, context=None):
    if context is None:
        context = build_post_match_context(
            home_team,
            away_team,
            home_score,
            away_score,
            stage,
            group=group,
            match_id=match_id,
            match_date=match_date
        )

    prompt = f"""
    You are MatchMind, a football analyst covering the 2026 FIFA World Cup.
    Write a post-match report for the following result:

    Result: {context["result"]}
    Stage: {context["stage"]}
    Outcome: {context["outcome"]}

    AVAILABLE DATA

    {_context_block("Current standings", context["standings"])}

    {_context_block("Match data", context["match_data"])}

    Write this like a match report from a quality sports publication — analytical,
    alive, with a sense of occasion. Be vivid where the moment earns it, precise
    where the data demands it. Never hollow, never over the top.

    Structure your report as follows:
    - A headline and strong opening paragraph that captures the result, the stakes,
      and why it mattered in the group.
    - A chronological match narrative built from the goals, half-time score, cards,
      substitutions, and other listed events. If red cards are listed, explain how
      they changed the match without inventing details beyond the event timeline.
    - A statistics paragraph using expected goals, shots, shots on target,
      possession, corners, big chances, or saves when those numbers are present.
    - A personnel paragraph using the listed lineups/squads, formations, starters,
      substitutes, and important player involvement where present.
    - A group-standings paragraph explaining what the result means for both teams,
      based strictly on the standings table above.
    - A concise closing paragraph about what each side takes into the next match.

    ABSOLUTE RULES — these cannot be broken under any circumstances:
    - Your report must be driven by the AVAILABLE DATA above. If match events,
      statistics, venue, referee, or standings are available, use them directly
      and specifically in the report.
    - If goals, red cards, half-time score, xG, shots on target, or lineups are
      present in Match data, they must appear in the report.
    - If match data says "Not available", write a shorter result-focused report
      and state that detailed event/statistical data is not available. Do not
      create a match narrative from imagination.
    - Only mention player names, referees, or venues that explicitly appear in the
      data above. Do not recall, invent, or assume any names from your training data.
    - Do not invent minute-by-minute events, cards, substitutions, or stats that
      are not present in the data above.
    - Do not characterize the disciplinary tone of the match in any way beyond
      what the data explicitly shows.
    - No exclamation marks. Confident, measured tone throughout.
    - If detailed match data is available, write 500-750 words. If match data is
      not available, keep it under 250 words.
    """

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    briefing = generate_match_briefing("Mexico", "South Africa", "2026-06-11", "GROUP_STAGE", "GROUP_A", match_id=537327)
    print("BRIEFING:\n", briefing)

    report = generate_post_match_report("Mexico", "South Africa", 2, 0, "GROUP_STAGE", "GROUP_A", match_id=537327, match_date="2026-06-11")
    print("\nREPORT:\n", report)